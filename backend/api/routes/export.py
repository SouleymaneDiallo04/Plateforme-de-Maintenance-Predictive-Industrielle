"""Export PDF rapport de maintenance et CSV benchmark."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from backend.ml.health_tracker import fleet_manager
from backend.ml.model_registry import registry

router = APIRouter(tags=["Export"])

# ── Couleurs PrognoSense ──────────────────────────────────────────────────
CYAN      = colors.HexColor("#00D4FF")
GREEN     = colors.HexColor("#00FF9F")
RED       = colors.HexColor("#FF3366")
ORANGE    = colors.HexColor("#FF6B35")
DARK_BG   = colors.HexColor("#0A0E1A")
DARK_CARD = colors.HexColor("#111827")
GREY      = colors.HexColor("#4A6FA5")


@router.get("/export/report/{machine_id}")
def export_report_pdf(machine_id: str):
    """Génère un rapport PDF professionnel de maintenance."""
    machine = fleet_manager.get_machine(machine_id)
    if not machine:
        raise HTTPException(404, f"Machine {machine_id} introuvable")

    state   = machine.get_current_state()
    history = machine.get_history()
    diag    = state.get("last_diagnosis") or {}
    trend   = state.get("trend", {})
    alerts  = machine._alerts[-10:]

    # ── Génération PDF en mémoire ─────────────────────────────────────────
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize    = A4,
        rightMargin = 2*cm, leftMargin = 2*cm,
        topMargin   = 2*cm, bottomMargin = 2*cm,
    )

    styles  = getSampleStyleSheet()
    story   = []

    # Style titre
    title_style = ParagraphStyle(
        "TitleStyle",
        parent    = styles["Title"],
        fontSize  = 22,
        textColor = CYAN,
        spaceAfter= 6,
        alignment = TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent    = styles["Normal"],
        fontSize  = 10,
        textColor = GREY,
        alignment = TA_CENTER,
        spaceAfter= 20,
    )
    h2_style = ParagraphStyle(
        "H2Style",
        parent    = styles["Heading2"],
        fontSize  = 13,
        textColor = CYAN,
        spaceBefore= 16,
        spaceAfter = 6,
    )
    normal_style = ParagraphStyle(
        "NormalStyle",
        parent    = styles["Normal"],
        fontSize  = 10,
        textColor = colors.HexColor("#E8F4FD"),
        spaceAfter= 4,
    )

    # ── En-tête ───────────────────────────────────────────────────────────
    story.append(Paragraph("PROGNOSENSE", title_style))
    story.append(Paragraph(
        "Rapport de Maintenance Prédictive par l'IA",
        subtitle_style
    ))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=CYAN, spaceAfter=12
    ))

    # Infos générales
    info_data = [
        ["Machine"  , machine_id,
         "Date"     , datetime.now().strftime("%d/%m/%Y %H:%M")],
        ["Dataset"  , machine.dataset,
         "Généré par", "PrognoSense v1.0"],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 6*cm, 3*cm, 6*cm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,0), (0,-1), CYAN),
        ("TEXTCOLOR",   (2,0), (2,-1), CYAN),
        ("TEXTCOLOR",   (1,0), (1,-1), colors.white),
        ("TEXTCOLOR",   (3,0), (3,-1), colors.white),
        ("BACKGROUND",  (0,0), (-1,-1), DARK_CARD),
        ("GRID",        (0,0), (-1,-1), 0.5, GREY),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [DARK_CARD, DARK_BG]),
        ("PADDING",     (0,0), (-1,-1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # ── État de santé ─────────────────────────────────────────────────────
    story.append(Paragraph("ÉTAT DE SANTÉ", h2_style))

    hi    = state["health_index"]
    color_map = {
        "sain"        : GREEN,
        "surveillance": colors.HexColor("#FFB800"),
        "alerte"      : ORANGE,
        "critique"    : RED,
    }
    hi_color = color_map.get(state["status"], GREY)

    health_data = [
        ["Indicateur"        , "Valeur"          , "Interprétation"],
        ["Health Index"      , f"{hi:.1f}%"      , state["status"].upper()],
        ["RUL estimée"       , f"{state.get('rul', 'N/A')} cycles",
         "Durée de vie résiduelle"],
        ["Tendance"          , trend.get("slope", "N/A"),
         trend.get("description", "N/A")],
        ["Nombre d'alertes"  , str(state.get("n_alerts", 0)),
         "Alertes déclenchées"],
    ]
    health_table = Table(
        health_data,
        colWidths=[5*cm, 4*cm, 9*cm]
    )
    health_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), CYAN),
        ("TEXTCOLOR",   (0,0), (-1,0), DARK_BG),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,1), (-1,-1), colors.white),
        ("TEXTCOLOR",   (1,1), (1,1), hi_color),
        ("FONTNAME",    (1,1), (1,1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [DARK_CARD, DARK_BG]),
        ("GRID",        (0,0), (-1,-1), 0.5, GREY),
        ("PADDING",     (0,0), (-1,-1), 7),
    ]))
    story.append(health_table)
    story.append(Spacer(1, 8))

    # ── Diagnostic ────────────────────────────────────────────────────────
    if diag:
        story.append(Paragraph("DIAGNOSTIC", h2_style))
        diag_data = [
            ["Paramètre",   "Valeur"],
            ["Défaut détecté", diag.get("fault", "N/A")],
            ["Confiance",      f"{diag.get('confidence', 0)*100:.1f}%"],
            ["Sévérité",       diag.get("severity", "N/A").upper()],
            ["Message",        diag.get("message", "N/A")],
        ]
        diag_table = Table(diag_data, colWidths=[5*cm, 13*cm])
        diag_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1E2D4A")),
            ("TEXTCOLOR",   (0,0), (-1,0), CYAN),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("TEXTCOLOR",   (0,1), (-1,-1), colors.white),
            ("TEXTCOLOR",   (0,1), (0,-1), CYAN),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [DARK_CARD, DARK_BG]),
            ("GRID",        (0,0), (-1,-1), 0.5, GREY),
            ("PADDING",     (0,0), (-1,-1), 7),
        ]))
        story.append(diag_table)

        # Recommandation
        rec = diag.get("recommendation", {})
        if rec:
            story.append(Spacer(1, 8))
            rec_data = [
                ["Action recommandée", rec.get("action", "N/A")],
                ["Urgence",            rec.get("urgency", "N/A").upper()],
                ["Délai d'intervention", rec.get("delay", "N/A")],
            ]
            rec_table = Table(rec_data, colWidths=[5*cm, 13*cm])
            rec_table.setStyle(TableStyle([
                ("FONTSIZE",    (0,0), (-1,-1), 9),
                ("TEXTCOLOR",   (0,0), (0,-1), ORANGE),
                ("TEXTCOLOR",   (1,0), (1,-1), colors.white),
                ("FONTNAME",    (1,0), (1,0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0,0), (-1,-1), [DARK_CARD, DARK_BG]),
                ("GRID",        (0,0), (-1,-1), 0.5, GREY),
                ("PADDING",     (0,0), (-1,-1), 7),
            ]))
            story.append(rec_table)

    # ── Alertes récentes ──────────────────────────────────────────────────
    if alerts:
        story.append(Paragraph("ALERTES RÉCENTES", h2_style))
        alert_data = [["Horodatage", "Type", "Message", "HI"]]
        for a in alerts[-8:]:
            alert_data.append([
                a.get("timestamp", "")[:16].replace("T", " "),
                a.get("type", ""),
                a.get("message", "")[:60],
                f"{a.get('hi', 0):.1f}%",
            ])
        alert_table = Table(
            alert_data,
            colWidths=[3.5*cm, 3*cm, 9.5*cm, 2*cm]
        )
        alert_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1E2D4A")),
            ("TEXTCOLOR",   (0,0), (-1,0), CYAN),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 8),
            ("TEXTCOLOR",   (0,1), (-1,-1), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [DARK_CARD, DARK_BG]),
            ("GRID",        (0,0), (-1,-1), 0.5, GREY),
            ("PADDING",     (0,0), (-1,-1), 5),
        ]))
        story.append(alert_table)

    # ── Pied de page ──────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%", thickness=1, color=GREY
    ))
    story.append(Paragraph(
        f"Rapport généré par PrognoSense v1.0 — "
        f"ENSAM-Meknès {datetime.now().year} — "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ParagraphStyle(
            "Footer", parent=styles["Normal"],
            fontSize=8, textColor=GREY, alignment=TA_CENTER
        )
    ))

    doc.build(story)
    buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return StreamingResponse(
        buffer,
        media_type = "application/pdf",
        headers    = {
            "Content-Disposition":
                f'attachment; filename="rapport_{machine_id}_{timestamp}.pdf"'
        }
    )


@router.get("/export/benchmark")
def export_benchmark_csv():
    """Exporte les résultats du benchmark en CSV."""
    import csv

    results = registry.get_benchmark_results()
    classif = results.get("classification", {})
    output  = io.StringIO()
    writer  = csv.writer(output)

    writer.writerow([
        "Modèle", "Dataset", "Accuracy(%)",
        "F1-score", "Temps train(s)", "Inférence(ms)"
    ])

    if classif and "Modèle" in classif:
        modeles  = classif.get("Modèle", {})
        datasets = classif.get("Dataset", {})
        accs     = classif.get("Accuracy (%)", {})
        f1s      = classif.get("F1-score", {})
        trains   = classif.get("Temps train (s)", {})
        infers   = classif.get("Inférence (ms)", {})
        for k in modeles:
            writer.writerow([
                modeles.get(k, ""), datasets.get(k, ""),
                accs.get(k, ""),   f1s.get(k, ""),
                trains.get(k, ""), infers.get(k, ""),
            ])

    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type = "text/csv",
        headers    = {
            "Content-Disposition":
                f'attachment; filename="benchmark_{timestamp}.csv"'
        }
    )