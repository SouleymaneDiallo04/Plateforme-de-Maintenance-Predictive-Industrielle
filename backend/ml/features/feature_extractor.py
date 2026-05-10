"""
FeatureExtractor — calcule les indicateurs vibratoires classiques
sur des fenêtres UnifiedSignal.
Gère les deux types de signaux :
  - Temporel haute fréquence (VBL-VA001) : RMS, Kurtosis, FFT, etc.
  - Cycles consécutifs (CMAPSS) : statistiques sur les 21 capteurs.
"""

import numpy as np
from scipy.stats import kurtosis, skew
from scipy.fft import rfft, rfftfreq
from backend.ml.adapters.dataset_adapter import UnifiedSignal, TARGET_FS
import re
from scipy.signal import hilbert, butter, filtfilt


def extract_features(signal: UnifiedSignal) -> np.ndarray:
    """
    Entrée  : un UnifiedSignal
    Sortie  : vecteur de features 1D (numpy array)

    Dispatch automatique selon le type de signal :
    - sampling_rate = TARGET_FS → signal vibratoire temporel
    - sampling_rate = None      → signal par cycles (CMAPSS)
    """
    if signal.sampling_rate == TARGET_FS:
        return _features_vibration(signal)
    else:
        return _features_cycles(signal)


# ── Features pour signaux vibratoires (VBL, CWRU...) ──────────────────────

def _features_vibration(signal: UnifiedSignal) -> np.ndarray:
    """
    Calcule les features sur chaque fenêtre puis moyenne sur toutes les fenêtres.
    signal.signals shape : (n_windows, window_size, n_channels)
    """
    windows    = signal.signals          # (n_windows, 1024, n_channels)
    n_windows  = windows.shape[0]
    n_channels = windows.shape[2]

    all_features = []

    for w in range(n_windows):
        win      = windows[w]            # (1024, n_channels)
        features = []

        for c in range(n_channels):
            x = win[:, c].astype(np.float64)

            # ── Domaine temporel ──────────────────────────────
            rms       = np.sqrt(np.mean(x**2))
            kurt      = kurtosis(x, fisher=True)
            skewness  = skew(x)
            peak      = np.max(np.abs(x))
            p2p       = np.max(x) - np.min(x)
            crest     = peak / (rms + 1e-10)
            mean_abs  = np.mean(np.abs(x))
            shape_f   = rms / (mean_abs + 1e-10)
            impulse_f = peak / (mean_abs + 1e-10)
            std       = np.std(x)

            # ── Domaine fréquentiel (FFT) ─────────────────────
            N        = len(x)
            spectrum = np.abs(rfft(x)) / N
            freqs    = rfftfreq(N, d=1.0/TARGET_FS)

            # Énergie spectrale par bande (4 bandes)
            band_edges = [0, 1000, 3000, 5000, TARGET_FS//2]
            band_energy = []
            for i in range(len(band_edges)-1):
                mask  = (freqs >= band_edges[i]) & (freqs < band_edges[i+1])
                energy = np.sum(spectrum[mask]**2)
                band_energy.append(energy)

            # Fréquence dominante
            dom_freq_idx  = np.argmax(spectrum)
            dom_freq      = freqs[dom_freq_idx]

            # Entropie spectrale
            ps           = spectrum**2
            ps_norm      = ps / (ps.sum() + 1e-10)
            spectral_ent = -np.sum(ps_norm * np.log(ps_norm + 1e-10))

            features += [
                rms, kurt, skewness, peak, p2p,
                crest, shape_f, impulse_f, std,
                dom_freq, spectral_ent,
                *band_energy
            ]

        all_features.append(features)

    # Moyenne sur toutes les fenêtres
    return np.mean(all_features, axis=0).astype(np.float32)


# ── Features pour signaux par cycles (CMAPSS) ─────────────────────────────

def _features_cycles(signal: UnifiedSignal) -> np.ndarray:
    """
    Pour CMAPSS : signal.signals shape = (1, 30, 21)
    Calcule des statistiques sur les 30 cycles pour chaque capteur.
    """
    window = signal.signals[0]    # (30, 21) — 30 cycles × 21 capteurs
    features = []

    for c in range(window.shape[1]):
        x = window[:, c].astype(np.float64)

        mean_val  = np.mean(x)
        std_val   = np.std(x)
        min_val   = np.min(x)
        max_val   = np.max(x)
        trend     = np.polyfit(np.arange(len(x)), x, 1)[0]  # pente linéaire
        kurt_val  = kurtosis(x, fisher=True)

        features += [mean_val, std_val, min_val, max_val, trend, kurt_val]

    return np.array(features, dtype=np.float32)


# ── Extraction en batch ────────────────────────────────────────────────────

def extract_features_batch(signals: list,
                            verbose: bool = True) -> tuple:
    """
    Extrait les features de toute une liste de UnifiedSignal.

    Retourne :
        X : np.ndarray (n_signals, n_features)
        y : list de labels
        meta : list de dict (unit_id, rul, cycle pour CMAPSS)
    """
    X, y, meta = [], [], []

    for i, sig in enumerate(signals):
        if verbose and i % 100 == 0:
            print(f"  Features extraites : {i}/{len(signals)}")
        try:
            feat = extract_features(sig)
            X.append(feat)
            y.append(sig.label)
            meta.append({
                "unit_id": sig.unit_id,
                "rul":     sig.rul,
                "cycle":   sig.cycle,
                "source":  sig.source
            })
        except Exception as e:
            print(f"  ERREUR signal {sig.unit_id}: {e}")

    return np.array(X, dtype=np.float32), y, meta

def extract_features_per_window(signals: list,
                                  verbose: bool = True) -> tuple:
    """
    Version qui traite CHAQUE FENÊTRE individuellement.
    
    Au lieu de : 1 UnifiedSignal → 1 vecteur de features (moyenne)
    On fait    : 1 UnifiedSignal → N vecteurs (1 par fenêtre)
    
    Retourne :
        X    : (n_total_fenetres, n_features)
        y    : labels (répété pour chaque fenêtre)
        meta : métadonnées avec index de fenêtre
    """
    X, y, meta = [], [], []

    for i, sig in enumerate(signals):
        if verbose and i % 20 == 0:
            print(f"  Signal {i}/{len(signals)} — {sig.unit_id}")

        n_windows  = sig.signals.shape[0]
        n_channels = sig.signals.shape[2]

        for w_idx in range(n_windows):
            # Créer un UnifiedSignal temporaire avec 1 seule fenêtre
            window_sig = UnifiedSignal(
                signals       = sig.signals[w_idx:w_idx+1],  # (1, 1024, n_ch)
                sampling_rate = sig.sampling_rate,
                label         = sig.label,
                unit_id       = sig.unit_id,
                cycle         = sig.cycle,
                rul           = sig.rul,
                source        = sig.source
            )

            try:
                feat = extract_features(window_sig)
                X.append(feat)
                y.append(sig.label)
                meta.append({
                    "unit_id"   : sig.unit_id,
                    "window_idx": w_idx,
                    "rul"       : sig.rul,
                    "cycle"     : sig.cycle,
                    "source"    : sig.source
                })
            except Exception as e:
                print(f"    ERREUR {sig.unit_id} fenêtre {w_idx}: {e}")

    print(f"\n  Total : {len(X)} fenêtres extraites")
    return np.array(X, dtype=np.float32), y, meta


def extract_rpm_from_uid(unit_id: str) -> float:
    """
    Extrait le RPM depuis le nom de fichier MCC5-THU.
    Ex: 'gear_wear_H_speed_circulation_10Nm-2000rpm' → 2000.0
    """
    match = re.search(r'(\d{3,4})rpm', unit_id)
    if match:
        return float(match.group(1))
    # Fallback : chercher dans le format speed
    match2 = re.search(r'-(\d{3,4})rpm', unit_id)
    if match2:
        return float(match2.group(1))
    return 2000.0   # valeur par défaut si non trouvé


def extract_gear_features(signal_1d: np.ndarray,
                           fs: float,
                           rpm: float) -> np.ndarray:
    """
    Features spécialisées pour défauts d'engrenages.
    
    signal_1d : signal 1D (une fenêtre, un canal)
    fs        : fréquence d'échantillonnage (Hz)
    rpm       : vitesse de rotation (tr/min)
    
    Retourne un vecteur de features supplémentaires.
    """
    features = []
    N        = len(signal_1d)
    x        = signal_1d.astype(np.float64)
    shaft_freq = rpm / 60.0   # fréquence de rotation en Hz

    # ── 1. Spectre FFT normalisé ───────────────────────────────────────────
    spectrum = np.abs(rfft(x)) / N
    freqs    = rfftfreq(N, d=1.0/fs)

    # ── 2. Gear Mesh Frequency (GMF) ──────────────────────────────────────
    # MCC5-THU : réducteur avec ~20 dents (estimation standard)
    # La GMF exacte n'est pas documentée → on teste 3 valeurs typiques
    # et on prend l'énergie max autour de chaque candidat
    n_teeth_candidates = [18, 20, 24]   # nombres de dents typiques
    gmf_energies = []
    for n_teeth in n_teeth_candidates:
        gmf = shaft_freq * n_teeth
        # Énergie dans une bande ±5% autour de GMF
        for harmonic in [1, 2, 3]:
            f_center = gmf * harmonic
            f_low    = f_center * 0.95
            f_high   = f_center * 1.05
            if f_high < fs / 2:
                mask   = (freqs >= f_low) & (freqs <= f_high)
                energy = np.sum(spectrum[mask]**2)
                gmf_energies.append(energy)
            else:
                gmf_energies.append(0.0)

    features += gmf_energies   # 9 features (3 candidats × 3 harmoniques)

    # ── 3. Sidebands autour de GMF (bandes latérales) ─────────────────────
    # Les sidebands à GMF ± k*shaft_freq indiquent une modulation
    # = signature classique de défaut d'engrenage
    gmf_nominal = shaft_freq * 20   # GMF avec 20 dents
    sideband_energies = []
    for k in [1, 2, 3]:
        for sign in [-1, 1]:
            f_sb   = gmf_nominal + sign * k * shaft_freq
            f_low  = f_sb * 0.95
            f_high = f_sb * 1.05
            if 0 < f_low and f_high < fs / 2:
                mask   = (freqs >= f_low) & (freqs <= f_high)
                energy = np.sum(spectrum[mask]**2)
                sideband_energies.append(energy)
            else:
                sideband_energies.append(0.0)

    features += sideband_energies   # 6 features

    # ── 4. Ratio sidebands / GMF (indicateur de modulation) ───────────────
    gmf_mask       = (freqs >= gmf_nominal*0.95) & (freqs <= gmf_nominal*1.05)
    gmf_energy     = np.sum(spectrum[gmf_mask]**2) + 1e-10
    total_sideband = sum(sideband_energies) + 1e-10
    sideband_ratio = total_sideband / gmf_energy
    features.append(sideband_ratio)   # 1 feature

    # ── 5. Démodulation d'enveloppe (Hilbert transform) ───────────────────
    # Filtrage passe-bande autour de la résonance haute fréquence
    # (typiquement 3-6 kHz pour engrenages)
    try:
        b, a = butter(4, [3000/(fs/2), 6000/(fs/2)], btype='band')
        x_filtered = filtfilt(b, a, x)
        envelope   = np.abs(hilbert(x_filtered))

        env_rms    = np.sqrt(np.mean(envelope**2))
        env_kurt   = float(kurtosis(envelope, fisher=True))
        env_std    = np.std(envelope)
        env_peak   = np.max(envelope)
        env_crest  = env_peak / (env_rms + 1e-10)

        # Spectre de l'enveloppe
        env_spectrum = np.abs(rfft(envelope)) / len(envelope)
        env_freqs    = rfftfreq(len(envelope), d=1.0/fs)

        # Énergie à la fréquence de rotation et harmoniques
        shaft_energies = []
        for k in [1, 2, 3, 4]:
            f_center = shaft_freq * k
            mask     = (env_freqs >= f_center*0.9) & (env_freqs <= f_center*1.1)
            shaft_energies.append(np.sum(env_spectrum[mask]**2))

        features += [env_rms, env_kurt, env_std, env_crest]
        features += shaft_energies   # 4 features

    except Exception:
        features += [0.0] * 8

    # ── 6. Cepstrum (détecte familles harmoniques périodiques) ────────────
    try:
        log_spectrum  = np.log(np.abs(rfft(x)) + 1e-10)
        cepstrum      = np.abs(rfft(log_spectrum))
        # Quefrency correspondant à la période de rotation
        quefrency_rot = fs / (shaft_freq + 1e-10)
        idx_rot       = int(quefrency_rot)
        if 0 < idx_rot < len(cepstrum):
            cep_peak_rot  = cepstrum[idx_rot]
            cep_peak_area = np.sum(cepstrum[max(0,idx_rot-3):idx_rot+4])
        else:
            cep_peak_rot  = 0.0
            cep_peak_area = 0.0
        features += [cep_peak_rot, cep_peak_area]   # 2 features
    except Exception:
        features += [0.0, 0.0]

    return np.array(features, dtype=np.float32)
    # Total : 9 + 6 + 1 + 8 + 2 = 26 features spécialisées engrenages

def extract_features_mcc5_v2(signals: list,
                               verbose: bool = True) -> tuple:
    """
    Approche v2 : features spectrales relatives au RPM.
    Au lieu de calculer GMF avec nombre de dents inconnu,
    on normalise le spectre par la fréquence de rotation
    et on extrait des features dans des bandes relatives.
    """
    X, y, meta = [], [], []

    for i, sig in enumerate(signals):
        if verbose and i % 20 == 0:
            print(f"  Signal {i}/{len(signals)} — {sig.unit_id}")

        rpm = extract_rpm_from_uid(sig.unit_id)
        nm_match = re.search(r'(\d+)Nm', sig.unit_id)
        nm = float(nm_match.group(1)) if nm_match else 10.0
        shaft_freq = rpm / 60.0

        n_windows = sig.signals.shape[0]

        for w_idx in range(n_windows):
            window = sig.signals[w_idx]  # (1024, 3)
            try:
                feat_all = []

                for ch in range(3):  # x, y, z
                    x = window[:, ch].astype(np.float64)
                    N = len(x)

                    # ── Features temporelles de base ──────────────────────
                    rms      = np.sqrt(np.mean(x**2))
                    kurt_val = float(kurtosis(x, fisher=True))
                    skew_val = float(skew(x))
                    p2p      = np.max(x) - np.min(x)
                    crest    = np.max(np.abs(x)) / (rms + 1e-10)
                    std_val  = np.std(x)

                    feat_all += [rms, kurt_val, skew_val, p2p, crest, std_val]

                    # ── Spectre FFT ───────────────────────────────────────
                    spectrum = np.abs(rfft(x)) / N
                    freqs    = rfftfreq(N, d=1.0/TARGET_FS)

                    # ── Bandes spectrales RELATIVES à shaft_freq ──────────
                    # On divise le spectre en bandes de k*shaft_freq
                    # Ça marche peu importe le nombre de dents
                    band_energies = []
                    for k in range(1, 21):   # 20 harmoniques de shaft_freq
                        f_low  = (k - 0.4) * shaft_freq
                        f_high = (k + 0.4) * shaft_freq
                        if f_high < TARGET_FS / 2:
                            mask   = (freqs >= f_low) & (freqs <= f_high)
                            energy = np.sum(spectrum[mask]**2)
                        else:
                            energy = 0.0
                        band_energies.append(energy)
                    feat_all += band_energies   # 20 features par canal

                    # ── Enveloppe Hilbert ─────────────────────────────────
                    try:
                        b, a = butter(
                            4,
                            [2000/(TARGET_FS/2), 6000/(TARGET_FS/2)],
                            btype='band'
                        )
                        x_bp   = filtfilt(b, a, x)
                        env    = np.abs(hilbert(x_bp))
                        env_rms  = np.sqrt(np.mean(env**2))
                        env_kurt = float(kurtosis(env, fisher=True))
                        env_std  = np.std(env)
                    except Exception:
                        env_rms, env_kurt, env_std = 0.0, 0.0, 0.0

                    feat_all += [env_rms, env_kurt, env_std]   # 3 features

                # ── Feature contextuelle : RPM et charge normalisés ───────
                feat_all += [rpm / 3000.0, nm / 20.0]   # 2 features

                # Total : 3 canaux × (6 + 20 + 3) + 2 = 89 features
                X.append(np.array(feat_all, dtype=np.float32))
                y.append(sig.label)
                meta.append({
                    "unit_id"   : sig.unit_id,
                    "window_idx": w_idx,
                    "rpm"       : rpm,
                    "nm"        : nm,
                    "source"    : sig.source
                })

            except Exception as e:
                print(f"  ERREUR {sig.unit_id} w{w_idx}: {e}")

    print(f"\n  Total : {len(X)} fenêtres extraites")
    return np.array(X, dtype=np.float32), y, meta
# Fréquence de rotation Mechanical Faults (constante)
MF_SHAFT_FREQ = 1238 / 60   # ≈ 20.63 Hz


def extract_features_mechanical_faults(signals: list,
                                        verbose: bool = True) -> tuple:
    """
    Extraction spécialisée pour Mechanical Faults Mendeley.
    
    Particularités :
    - Vitesse constante 1238 RPM → fréquences de rotation connues
    - 4 canaux (2 positions × 2 axes)
    - Fenêtre 4096 points → résolution 3.125 Hz → voit les harmoniques
    
    Features par canal (32 features) :
    - 6 features temporelles (RMS, Kurtosis, Skewness, P2P, Crest, Std)
    - 10 features harmoniques (énergie à 1x,2x,...,5x × 2 bandes)
    - 6 features bandes spectrales larges
    - 5 features enveloppe Hilbert
    - 5 features ratio harmoniques (signatures déséquilibre vs désalignement)
    
    Total : 4 canaux × 32 + 0 ctx = 128 features
    """
    X, y, meta = [], [], []

    for i, sig in enumerate(signals):
        if verbose and i % 100 == 0:
            print(f"  Signal {i}/{len(signals)} — {sig.unit_id}")

        n_windows = sig.signals.shape[0]

        for w_idx in range(n_windows):
            window = sig.signals[w_idx]   # (4096, 4)
            try:
                feat_all = []

                for ch in range(4):
                    x  = window[:, ch].astype(np.float64)
                    N  = len(x)
                    fs = TARGET_FS

                    # ── Features temporelles (6) ──────────────────────────
                    rms      = np.sqrt(np.mean(x**2))
                    kurt_val = float(kurtosis(x, fisher=True))
                    skew_val = float(skew(x))
                    p2p      = np.max(x) - np.min(x)
                    crest    = np.max(np.abs(x)) / (rms + 1e-10)
                    std_val  = np.std(x)
                    feat_all += [rms, kurt_val, skew_val, p2p, crest, std_val]

                    # ── Spectre FFT haute résolution ──────────────────────
                    spectrum = np.abs(rfft(x)) / N
                    freqs    = rfftfreq(N, d=1.0/fs)
                    # Résolution : fs/N = 12800/4096 = 3.125 Hz ✅

                    # ── Features harmoniques rotation (10) ────────────────
                    # Déséquilibre    : pic fort à 1x
                    # Désalignement   : pics à 2x et 3x
                    # Jeu mécanique   : sous-harmoniques (0.5x) + largebande
                    harmonic_feats = []
                    for k_num, k_den in [(1,1),(2,1),(3,1),(4,1),(5,1),
                                          (1,2),(3,2),(1,3),(2,3),(1,4)]:
                        f_center = MF_SHAFT_FREQ * k_num / k_den
                        # Bande ±10% autour de l'harmonique
                        f_low  = f_center * 0.90
                        f_high = f_center * 1.10
                        if 0 < f_low and f_high < fs/2:
                            mask   = (freqs >= f_low) & (freqs <= f_high)
                            energy = np.sum(spectrum[mask]**2)
                        else:
                            energy = 0.0
                        harmonic_feats.append(energy)
                    feat_all += harmonic_feats   # 10 features
                    # Énergie totale du signal (déjà dans RMS ?) mais ajouter ratio
                    energy_total = np.sum(spectrum**2)
                    harm1 = harmonic_feats[0]  # déjà calculé
                    ratio_total_harm1 = energy_total / (harm1 + 1e-10)
                    feat_all.append(ratio_total_harm1)

                    # ── Bandes spectrales larges (6) ──────────────────────
                    band_edges = [0, 50, 200, 500, 1000, 3000, 6400]
                    for j in range(len(band_edges)-1):
                        mask   = ((freqs >= band_edges[j]) &
                                  (freqs < band_edges[j+1]))
                        energy = np.sum(spectrum[mask]**2)
                        feat_all.append(energy)   # 6 features

                    # ── Enveloppe Hilbert (5) ─────────────────────────────
                    try:
                        b, a = butter(
                            4,
                            [10/(fs/2), 500/(fs/2)],
                            btype='band'
                        )
                        x_bp     = filtfilt(b, a, x)
                        envelope = np.abs(hilbert(x_bp))

                        env_rms  = np.sqrt(np.mean(envelope**2))
                        env_kurt = float(kurtosis(envelope, fisher=True))
                        env_std  = np.std(envelope)

                        # Énergie enveloppe à 1x et 2x rotation
                        env_spec  = np.abs(rfft(envelope)) / len(envelope)
                        env_freqs = rfftfreq(len(envelope), d=1.0/fs)

                        def env_energy_at(f_c):
                            m = ((env_freqs >= f_c*0.85) &
                                 (env_freqs <= f_c*1.15))
                            return float(np.sum(env_spec[m]**2))

                        e1x = env_energy_at(MF_SHAFT_FREQ)
                        e2x = env_energy_at(MF_SHAFT_FREQ * 2)

                        feat_all += [env_rms, env_kurt, env_std, e1x, e2x]

                    except Exception:
                        feat_all += [0.0] * 5

                    # ── Ratios harmoniques — signature physique (5) ────────
                    # Déséquilibre    : E(1x) >> E(2x)  → ratio élevé
                    # Désalignement   : E(2x) ≈ E(1x)   → ratio ≈ 1
                    # Jeu mécanique   : énergie diffuse  → ratio faible
                    h1 = harmonic_feats[0] + 1e-10   # 1x
                    h2 = harmonic_feats[1] + 1e-10   # 2x
                    h3 = harmonic_feats[2] + 1e-10   # 3x
                    h4 = harmonic_feats[3] + 1e-10   # 4x

                    feat_all += [
                        h1 / h2,          # ratio 1x/2x (déséquilibre)
                        h2 / h3,          # ratio 2x/3x (désalignement)
                        h1 / (h2+h3+h4),  # dominance fondamentale
                        (h2+h3) / h1,     # richesse harmonique
                        h3 / h4,          # harmoniques supérieurs
                    ]   # 5 features

                # Total : 4 × (6+10+6+5+5) = 4 × 32 = 128 features
                X.append(np.array(feat_all, dtype=np.float32))
                y.append(sig.label)
                meta.append({
                    'unit_id'    : sig.unit_id,
                    'window_idx' : w_idx,
                    'source'     : sig.source
                })

            except Exception as e:
                print(f"  ERREUR {sig.unit_id} w{w_idx}: {e}")

    print(f"\n  Total : {len(X)} fenêtres extraites")
    return np.array(X, dtype=np.float32), y, meta