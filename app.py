
"""
Ewidencja zakupu i sprzedaży złomu elektrycznego.

Instalacja:
    pip install -r requirements.txt

Uruchomienie:
    streamlit run app.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

import database as db
from database import AppError

st.set_page_config(
    page_title="Ewidencja złomu elektrycznego",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&display=swap" rel="stylesheet">
    <style>
      html, body, [class*="css"], .stApp, p, div, span, label, input {
        font-family: "DM Sans", "Segoe UI", sans-serif;
      }
      .stApp {
        background:
          linear-gradient(180deg, #f7f7f5 0%, #eeeeea 100%);
      }
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stSidebar"] {
        background: #373737;
        border-right: 4px solid #f2c300;
      }
      [data-testid="stSidebar"] * { color: #f6f6f6 !important; }
      [data-testid="stSidebar"] .stRadio label { font-weight: 600; padding: 3px 0; }
      [data-testid="stSidebar"] [data-checked="true"] + div { color: #f7cf1a !important; }
      .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1360px; }
      h1, h2, h3 { color: #303030; letter-spacing: -0.01em; }
      div[data-testid="stMetric"] {
        background: #fff;
        border: 1px solid #d2d2d2;
        border-top: 3px solid #f2c300;
        padding: 0.75rem 0.9rem;
        border-radius: 3px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
      }
      .hero {
        background: #ffffff;
        border: 1px solid #d4d4d4;
        border-left: 7px solid #f2c300;
        border-radius: 3px;
        padding: 17px 21px;
        margin-bottom: 14px;
        color: #303030;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.07);
      }
      .hero h1 { color: #303030; font-size: 1.42rem; margin: 0 0 4px 0; font-weight: 700; }
      .hero p { color: #6b6b6b; margin: 0; font-size: 0.92rem; }
      .hint { color: #686868; font-size: 0.9rem; margin-bottom: 0.8rem; }
      .line-head {
        color: #3e3e3e;
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        background: #e9e9e7;
        border-top: 1px solid #c9c9c7;
        border-bottom: 1px solid #c9c9c7;
        padding: 7px 8px;
        margin-bottom: 0;
      }
      div[data-testid="stForm"] {
        background: #fff;
        border: 1px solid #d2d2d2;
        border-top: 3px solid #f2c300;
        border-radius: 3px;
        padding: 8px 12px 12px 12px;
      }
      .stButton > button {
        border-radius: 3px;
        font-weight: 600;
      }
      .stButton > button[kind="primary"] {
        background: #f2c300;
        border: 1px solid #d3a900;
        color: #292929;
      }
      .stButton > button[kind="secondary"] {
        background: #fff;
        border: 1px solid #bdbdbb;
        color: #343434;
      }
      [data-baseweb="input"], [data-baseweb="select"] > div {
        background: #fff !important;
        border-radius: 2px !important;
        border-color: #adadab !important;
      }
      [data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
        border-color: #d7aa00 !important;
        box-shadow: 0 0 0 1px #f2c300 !important;
      }
      [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 2px solid #c9c9c7;
      }
      [data-testid="stTabs"] button[role="tab"] {
        height: 38px;
        padding: 0 18px;
        border-radius: 3px 3px 0 0;
        color: #555 !important;
        font-weight: 600;
      }
      [data-testid="stTabs"] button[aria-selected="true"] {
        background: #f2c300 !important;
        color: #292929 !important;
      }
      [data-testid="stDataFrame"] {
        border: 1px solid #c9c9c7;
        border-top: 3px solid #f2c300;
        border-radius: 3px;
        overflow: hidden;
        background: #fff;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
      }
      [data-testid="stDataFrame"] [role="columnheader"] {
        background: #e9e9e7 !important;
        color: #353535 !important;
        font-weight: 700 !important;
        border-bottom: 1px solid #bdbdbb !important;
      }
      [data-testid="stDataFrame"] [role="gridcell"] {
        border-bottom: 1px solid #e5e5e3 !important;
      }
      [data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {
        background: #fff7cf !important;
      }
      [data-testid="stDataFrame"] [aria-selected="true"] [role="gridcell"] {
        background: #ffe98a !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",") + " zł"


def qty(value: float) -> str:
    return f"{float(value):g}"


def kg(value: float) -> str:
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " kg"


def show_error(exc: Exception) -> None:
    st.error(str(exc))


PBKDF2_ITERATIONS = 300_000


def hash_password(password: str) -> str:
    """Create a salted password hash; plain-text passwords are never stored."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, saved_digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        ).hex()
        return hmac.compare_digest(calculated, saved_digest)
    except (AttributeError, ValueError):
        return False


def bootstrap_initial_admin() -> None:
    """Create the first admin once, using values only from Streamlit Secrets."""
    if db.user_count() > 0:
        return
    try:
        username = str(st.secrets["INITIAL_ADMIN_LOGIN"])
        password = str(st.secrets["INITIAL_ADMIN_PASSWORD"])
    except Exception:
        return
    if username.strip() and password:
        try:
            db.create_user(username, hash_password(password), is_admin=True)
        except AppError:
            # Another Streamlit worker may create the same initial user first.
            pass


db.init_db()
bootstrap_initial_admin()


def option_map(rows: list[dict], label_fn) -> dict[str, int]:
    return {label_fn(r): int(r["id"]) for r in rows}


def selected_id_from_df(event, rows: list[dict]) -> int | None:
    sel = event.selection.rows if event and event.selection else []
    if not sel:
        return None
    idx = sel[0]
    if 0 <= idx < len(rows):
        return int(rows[idx]["id"])
    return None


def product_label(p: dict) -> str:
    return f"{p['sku']} — {p['name']}"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a scalable font both locally and on Streamlit Cloud.

    Streamlit Cloud uses a slim Linux image.  When its system font is absent,
    Pillow's old ``load_default()`` fallback is only a tiny bitmap font and
    ignores our requested label size.  Pillow 10.1+ can scale its embedded
    fallback font, so the label remains readable even without a system font.
    """
    candidates = []
    if bold:
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Kept only for a developer machine with an older Pillow release.
        return ImageFont.load_default()


def _barcode_png(code: str) -> Image.Image:
    buf = BytesIO()
    Code128(code, writer=ImageWriter()).write(
        buf,
        {
            "module_width": 0.45,
            "module_height": 24.0,
            "font_size": 0,
            "text_distance": 1,
            "quiet_zone": 2.0,
            "write_text": False,
        },
    )
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def render_label_png(data: dict) -> bytes:
    """Render a high-contrast 100 x 150 mm pallet label at 300 DPI.

    The label is deliberately laid out for reading from a short distance:
    pallet number, goods name and weights use the largest type on the page.
    """
    dpi = 300
    width = int(100 / 25.4 * dpi)
    height = int(150 / 25.4 * dpi)
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    margin = 32
    x0, y0 = margin, margin
    x1, y1 = width - margin, height - margin

    # A black-and-white layout remains readable on common thermal printers.
    draw.rectangle((x0, y0, x1, y1), outline="#000000", width=5)

    # Header
    y_header = 195
    draw.line((x0, y_header, x1, y_header), fill="#000000", width=4)
    draw.text((x0 + 22, y0 + 18), "ETYKIETA PALETY", font=_font(46, True), fill="#000000")
    draw.text((x0 + 22, y0 + 78), "ZŁOM ELEKTRYCZNY", font=_font(29, True), fill="#000000")
    draw.text((x0 + 22, y0 + 120), "FORMAT 100 × 150 mm", font=_font(21), fill="#000000")

    date_x = x1 - 340
    draw.line((date_x, y0, date_x, y_header), fill="#000000", width=3)
    draw.text((date_x + 20, y0 + 28), "DATA:", font=_font(23, True), fill="#000000")
    created_at = str(data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M"))
    draw.text((date_x + 20, y0 + 75), created_at[:16], font=_font(31, True), fill="#000000")

    # Pallet identifier - intentionally oversized for rapid manual reading.
    y_code = 435
    draw.line((x0, y_code, x1, y_code), fill="#000000", width=4)
    draw.text((x0 + 22, y_header + 18), "NUMER PALETY", font=_font(28, True), fill="#000000")
    code = str(data["code"])
    code_bbox = draw.textbbox((0, 0), code, font=_font(132, True))
    code_width = code_bbox[2] - code_bbox[0]
    draw.text(((width - code_width) // 2, y_header + 55), code, font=_font(132, True), fill="#000000")

    # Goods name and SKU
    y_product = 835
    draw.line((x0, y_product, x1, y_product), fill="#000000", width=4)
    draw.text((x0 + 22, y_code + 20), "TOWAR / ASORTYMENT", font=_font(28, True), fill="#000000")

    p_name = str(data.get("product") or "")
    words = p_name.split()
    lines_text = []
    cur_line = []
    for w in words:
        cur_line.append(w)
        bbox = draw.textbbox((0, 0), " ".join(cur_line), font=_font(68, True))
        if bbox[2] - bbox[0] > (x1 - x0 - 44):
            cur_line.pop()
            lines_text.append(" ".join(cur_line))
            cur_line = [w]
    if cur_line:
        lines_text.append(" ".join(cur_line))

    for i, lt in enumerate(lines_text[:2]):
        draw.text((x0 + 22, y_code + 72 + i * 78), lt, font=_font(68, True), fill="#000000")

    draw.text((x0 + 22, y_product - 64), "INDEKS: " + str(data.get("sku") or "—"), font=_font(34, True), fill="#000000")

    # Weights: large values, with labels above them.
    y_weights = 1195
    draw.line((x0, y_weights, x1, y_weights), fill="#000000", width=4)

    col_w = (x1 - x0) // 3
    c1_x = x0 + col_w
    c2_x = x0 + 2 * col_w
    draw.line((c1_x, y_product, c1_x, y_weights), fill="#000000", width=3)
    draw.line((c2_x, y_product, c2_x, y_weights), fill="#000000", width=3)
    draw.line((x0, y_product + 72, x1, y_product + 72), fill="#000000", width=2)

    def draw_col_centered(col_left: int, col_right: int, header: str, val_str: str) -> None:
        h_bbox = draw.textbbox((0, 0), header, font=_font(28, True))
        hw = h_bbox[2] - h_bbox[0]
        draw.text((col_left + (col_right - col_left - hw) // 2, y_product + 22), header, font=_font(28, True), fill="#000000")
        v_bbox = draw.textbbox((0, 0), val_str, font=_font(62, True))
        vw = v_bbox[2] - v_bbox[0]
        draw.text((col_left + (col_right - col_left - vw) // 2, y_product + 105), val_str, font=_font(62, True), fill="#000000")

    draw_col_centered(x0, c1_x, "MASA NETTO", kg(data["net_weight"]))
    draw_col_centered(c1_x, c2_x, "TARA", kg(data["tare_weight"]))
    draw_col_centered(c2_x, x1, "MASA BRUTTO", kg(data["gross_weight"]))

    # Barcode
    y_barcode = 1690
    draw.line((x0, y_barcode, x1, y_barcode), fill="#000000", width=4)
    draw.text((x0 + 22, y_weights + 18), "KOD KRESKOWY / CODE 128", font=_font(28, True), fill="#000000")

    bc_img = _barcode_png(code)
    bc_w = x1 - x0 - 90
    bc_h = 325
    bc_img = bc_img.resize((bc_w, bc_h), Image.Resampling.NEAREST)
    img.paste(bc_img, (x0 + 45, y_weights + 63))

    code_str = f"* {code} *"
    c_bbox = draw.textbbox((0, 0), code_str, font=_font(74, True))
    cw = c_bbox[2] - c_bbox[0]
    draw.text(((width - cw) // 2, y_weights + 410), code_str, font=_font(74, True), fill="#000000")

    # Footer (kept below the barcode and within the print-safe area)
    draw.text((x0 + 22, y_barcode + 12), "SYSTEM EWIDENCJI ZŁOMU", font=_font(18, True), fill="#000000")
    draw.text((x1 - 230, y_barcode + 12), "CODE 128", font=_font(18, True), fill="#000000")

    out = BytesIO()
    img.save(out, format="PNG", dpi=(dpi, dpi))
    return out.getvalue()


def render_label_pdf(png_bytes: bytes) -> bytes:
    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(100 * mm, 150 * mm))
    c.drawImage(ImageReader(BytesIO(png_bytes)), 0, 0, width=100 * mm, height=150 * mm)
    c.showPage()
    c.save()
    return buf.getvalue()


def page_products() -> None:
    st.subheader("Słownik «Nomenklatura»")
    st.markdown(
        '<div class="hint">Indeks musi być unikalny. Ceny ze słownika są podstawiane '
        "do dokumentów; w dokumencie można je skorygować. Kwoty w złotych (PLN).</div>",
        unsafe_allow_html=True,
    )

    products = db.list_products()
    col_list, col_form = st.columns([1.4, 1], gap="large")

    with col_list:
        st.markdown("**Lista towarów**")
        if products:
            view = pd.DataFrame(products)[
                ["sku", "name", "purchase_price", "sale_price"]
            ].rename(
                columns={
                    "sku": "Indeks",
                    "name": "Nazwa towaru",
                    "purchase_price": "Cena zakupu (zł)",
                    "sale_price": "Cena sprzedaży (zł)",
                }
            )
            event = st.dataframe(
                view,
                hide_index=True,
                width="stretch",
                on_select="rerun",
                selection_mode="single-row",
                key="products_table",
            )
            picked = selected_id_from_df(event, products)
        else:
            st.info("Słownik jest pusty. Dodaj pierwszy towar po prawej stronie.")
            picked = None

        if picked:
            st.caption(f"Wybrany rekord ID {picked}")
            if st.button("Usuń wybrany towar", type="secondary"):
                try:
                    db.delete_product(picked)
                    st.success("Towar został usunięty.")
                    st.rerun()
                except AppError as exc:
                    show_error(exc)

    with col_form:
        mode = st.radio(
            "Tryb",
            ["Nowy towar", "Edytuj zaznaczony"],
            horizontal=True,
            key="product_mode",
        )
        editing = mode.startswith("Edytuj")
        current = db.get_product(picked) if editing and picked else None
        if editing and not current:
            st.warning("Wybierz towar w tabeli po lewej stronie.")
            return

        with st.form("product_form", clear_on_submit=not editing):
            sku = st.text_input(
                "Indeks *",
                value=current["sku"] if current else "",
                max_chars=50,
            )
            name = st.text_input(
                "Nazwa towaru *",
                value=current["name"] if current else "",
            )
            purchase_price = st.number_input(
                "Cena zakupu (zł) *",
                min_value=0.0,
                step=1.0,
                value=float(current["purchase_price"]) if current else 0.0,
                format="%.2f",
            )
            sale_price = st.number_input(
                "Cena sprzedaży (zł) *",
                min_value=0.0,
                step=1.0,
                value=float(current["sale_price"]) if current else 0.0,
                format="%.2f",
            )
            submitted = st.form_submit_button(
                "Zapisz" if editing else "Dodaj",
                type="primary",
                width="stretch",
            )
            if submitted:
                try:
                    if editing and current:
                        db.update_product(
                            current["id"], sku, name, purchase_price, sale_price
                        )
                        st.success("Towar został zapisany.")
                    else:
                        db.add_product(sku, name, purchase_price, sale_price)
                        st.success("Towar został dodany do słownika.")
                    st.rerun()
                except AppError as exc:
                    show_error(exc)


def page_counterparties() -> None:
    st.subheader("Słownik «Kontrahenci»")
    rows = db.list_counterparties()
    col_list, col_form = st.columns([1.4, 1], gap="large")

    with col_list:
        st.markdown("**Lista kontrahentów**")
        if rows:
            view = pd.DataFrame(rows)[["name", "phone", "inn", "address"]].rename(
                columns={
                    "name": "Nazwa",
                    "phone": "Telefon",
                    "inn": "NIP",
                    "address": "Adres",
                }
            )
            event = st.dataframe(
                view,
                hide_index=True,
                width="stretch",
                on_select="rerun",
                selection_mode="single-row",
                key="cp_table",
            )
            picked = selected_id_from_df(event, rows)
        else:
            st.info("Słownik jest pusty. Dodaj kontrahenta po prawej stronie.")
            picked = None

        if picked:
            if st.button("Usuń wybranego kontrahenta"):
                try:
                    db.delete_counterparty(picked)
                    st.success("Kontrahent został usunięty.")
                    st.rerun()
                except AppError as exc:
                    show_error(exc)

    with col_form:
        mode = st.radio(
            "Tryb",
            ["Nowy kontrahent", "Edytuj zaznaczonego"],
            horizontal=True,
            key="cp_mode",
        )
        editing = mode.startswith("Edytuj")
        current = next((r for r in rows if r["id"] == picked), None) if editing else None
        if editing and not current:
            st.warning("Wybierz kontrahenta w tabeli po lewej stronie.")
            return

        with st.form("cp_form", clear_on_submit=not editing):
            name = st.text_input(
                "Nazwa kontrahenta *",
                value=current["name"] if current else "",
            )
            phone = st.text_input(
                "Numer telefonu", value=current["phone"] if current else ""
            )
            inn = st.text_input("NIP", value=current["inn"] if current else "")
            address = st.text_area(
                "Adres", value=current["address"] if current else "", height=80
            )
            submitted = st.form_submit_button(
                "Zapisz" if editing else "Dodaj",
                type="primary",
                width="stretch",
            )
            if submitted:
                try:
                    if editing and current:
                        db.update_counterparty(
                            current["id"], name, phone, inn, address
                        )
                        st.success("Kontrahent został zapisany.")
                    else:
                        db.add_counterparty(name, phone, inn, address)
                        st.success("Kontrahent został dodany.")
                    st.rerun()
                except AppError as exc:
                    show_error(exc)


def page_warehouses() -> None:
    st.subheader("Słownik «Magazyny»")
    rows = db.list_warehouses()
    col_list, col_form = st.columns([1.4, 1], gap="large")

    with col_list:
        st.markdown("**Lista magazynów**")
        if rows:
            view = pd.DataFrame(rows)[["name", "description"]].rename(
                columns={"name": "Nazwa magazynu", "description": "Opis / adres"}
            )
            st.dataframe(view, hide_index=True, width="stretch")
        else:
            st.info("Słownik jest pusty. Dodaj magazyn po prawej stronie.")

    with col_form:
        with st.form("wh_form", clear_on_submit=True):
            name = st.text_input("Nazwa magazynu *")
            description = st.text_area("Opis / adres", height=80)
            if st.form_submit_button(
                "Dodaj magazyn", type="primary", width="stretch"
            ):
                try:
                    db.add_warehouse(name, description)
                    st.success("Magazyn został dodany.")
                    st.rerun()
                except AppError as exc:
                    show_error(exc)


def ensure_lines(key: str) -> None:
    if key not in st.session_state:
        st.session_state[key] = []
    for line in st.session_state[key]:
        if "uid" not in line:
            line["uid"] = str(uuid.uuid4())


def render_lines_editor(
    state_key: str,
    price_field: str,
    warehouse_id: int | None,
) -> float:
    ensure_lines(state_key)
    products = db.list_products()
    if not products:
        st.warning("Najpierw uzupełnij słownik towarów.")
        return 0.0

    labels = option_map(products, product_label)
    by_id = {p["id"]: p for p in products}

    st.markdown("**Część tabelaryczna**")
    c1, c2, c3, c4 = st.columns([2.4, 1, 1, 0.9])
    with c1:
        chosen = st.selectbox("Towar", list(labels.keys()), key=f"{state_key}_prod")
        pid = labels[chosen]
        last_key = f"{state_key}_last_pid"
        price_key = f"{state_key}_price"
        if st.session_state.get(last_key) != pid:
            st.session_state[price_key] = float(by_id[pid][price_field])
            st.session_state[last_key] = pid
    with c2:
        quantity = st.number_input(
            "Ilość", min_value=0.001, value=1.0, step=1.0, key=f"{state_key}_qty"
        )
    with c3:
        price = st.number_input(
            "Cena (zł)",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key=price_key,
        )
    with c4:
        st.write("")
        st.write("")
        if st.button("Dodaj wiersz", key=f"{state_key}_add"):
            st.session_state[state_key].append(
                {
                    "uid": str(uuid.uuid4()),
                    "product_id": pid,
                    "sku": by_id[pid]["sku"],
                    "name": by_id[pid]["name"],
                    "quantity": float(quantity),
                    "price": float(price),
                    "amount": round(float(quantity) * float(price), 2),
                }
            )
            st.rerun()

    if warehouse_id:
        available = db.get_stock_qty(warehouse_id, pid)
        st.caption(f"Stan wybranego towaru w magazynie: {qty(available)}")

    lines = st.session_state[state_key]
    if not lines:
        st.info("Część tabelaryczna jest pusta. Dodaj wiersze.")
        return 0.0

    head = st.columns([1.15, 2.3, 1.15, 1.05, 1.1, 0.55])
    for col, title in zip(
        head,
        ["Indeks", "Towar", "Ilość", "Cena (zł)", "Wartość (zł)", ""],
    ):
        col.markdown(f'<div class="line-head">{title}</div>', unsafe_allow_html=True)

    for line in lines:
        cols = st.columns([1.15, 2.3, 1.15, 1.05, 1.1, 0.55])
        cols[0].markdown(f"**{line['sku']}**")
        cols[1].markdown(line["name"])
        new_qty = cols[2].number_input(
            "Ilość",
            min_value=0.001,
            value=float(line["quantity"]),
            step=1.0,
            key=f"{state_key}_edit_qty_{line['uid']}",
            label_visibility="collapsed",
        )
        cols[3].markdown(f"{float(line['price']):.2f}")
        line["quantity"] = float(new_qty)
        line["amount"] = round(float(new_qty) * float(line["price"]), 2)
        cols[4].markdown(f"**{line['amount']:.2f}**")
        if cols[5].button("✕", key=f"{state_key}_del_{line['uid']}", help="Usuń wiersz"):
            st.session_state[state_key] = [
                x for x in st.session_state[state_key] if x["uid"] != line["uid"]
            ]
            st.rerun()

    total = round(sum(x["amount"] for x in st.session_state[state_key]), 2)
    st.markdown(f"**Razem w dokumencie: {money(total)}**")
    return total


def render_document_view(doc: dict, kind: str) -> None:
    st.markdown(
        f"**Dokument {doc['number']}** z dnia {doc['doc_date']}  \n"
        f"Kontrahent: {doc['counterparty']}  \n"
        f"Magazyn: {doc['warehouse']}  \n"
        f"Wartość: {money(doc['total'])}"
    )
    if doc["lines"]:
        view = pd.DataFrame(doc["lines"])[
            ["sku", "product", "quantity", "price", "amount"]
        ].rename(
            columns={
                "sku": "Indeks",
                "product": "Towar",
                "quantity": "Ilość",
                "price": "Cena (zł)",
                "amount": "Wartość (zł)",
            }
        )
        st.dataframe(view, hide_index=True, width="stretch")


def page_purchases() -> None:
    st.subheader("Dziennik dokumentów «Zakupy»")
    tab_new, tab_journal = st.tabs(["Nowy dokument", "Dziennik"])

    with tab_new:
        cps = db.list_counterparties()
        whs = db.list_warehouses()
        if not cps or not whs:
            st.warning(
                "Aby wystawić zakup, w słownikach muszą być kontrahent i magazyn."
            )
            return

        c1, c2, c3 = st.columns(3)
        with c1:
            cp_map = option_map(cps, lambda r: r["name"])
            cp_label = st.selectbox("Kontrahent (dostawca) *", list(cp_map.keys()))
        with c2:
            wh_map = option_map(whs, lambda r: r["name"])
            wh_label = st.selectbox("Magazyn przyjęcia *", list(wh_map.keys()))
        with c3:
            doc_date = st.date_input("Data *", value=date.today())

        total = render_lines_editor(
            "purchase_lines", "purchase_price", wh_map[wh_label]
        )
        if st.button("Zatwierdź i zapisz zakup", type="primary"):
            try:
                number = db.create_purchase(
                    doc_date.isoformat(),
                    cp_map[cp_label],
                    wh_map[wh_label],
                    st.session_state.get("purchase_lines", []),
                )
                st.session_state.purchase_lines = []
                st.success(
                    f"Dokument {number} został zatwierdzony. Stany magazynowe wzrosły, "
                    f"z kasy pobrano {money(total)}."
                )
                st.rerun()
            except AppError as exc:
                show_error(exc)

    with tab_journal:
        docs = db.list_purchases()
        if not docs:
            st.info("Dziennik zakupów jest pusty.")
            return
        view = pd.DataFrame(docs)[
            ["number", "doc_date", "counterparty", "warehouse", "total"]
        ].rename(
            columns={
                "number": "Numer",
                "doc_date": "Data",
                "counterparty": "Kontrahent",
                "warehouse": "Magazyn",
                "total": "Wartość (zł)",
            }
        )
        event = st.dataframe(
            view,
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key="purchases_journal",
        )
        picked = selected_id_from_df(event, docs)
        if not picked:
            st.caption("Zaznacz dokument w tabeli, aby zobaczyć szczegóły.")
            return
        doc = db.get_purchase(picked)
        if not doc:
            st.error("Nie znaleziono dokumentu.")
            return
        render_document_view(doc, "purchase")
        if st.button("Usuń dokument (storno stanów i kasy)", type="secondary"):
            try:
                db.delete_purchase(picked)
                st.success("Dokument usunięty, stany i kasa zostały przeliczone.")
                st.rerun()
            except AppError as exc:
                show_error(exc)


def page_sales() -> None:
    st.subheader("Dziennik dokumentów «Sprzedaż»")
    tab_new, tab_journal = st.tabs(["Nowy dokument", "Dziennik"])

    with tab_new:
        cps = db.list_counterparties()
        whs = db.list_warehouses()
        if not cps or not whs:
            st.warning(
                "Aby wystawić sprzedaż, w słownikach muszą być kontrahent i magazyn."
            )
            return

        c1, c2, c3 = st.columns(3)
        with c1:
            cp_map = option_map(cps, lambda r: r["name"])
            cp_label = st.selectbox(
                "Kontrahent (nabywca) *", list(cp_map.keys()), key="sale_cp"
            )
        with c2:
            wh_map = option_map(whs, lambda r: r["name"])
            wh_label = st.selectbox(
                "Magazyn wydania *", list(wh_map.keys()), key="sale_wh"
            )
        with c3:
            doc_date = st.date_input("Data *", value=date.today(), key="sale_date")

        total = render_lines_editor("sale_lines", "sale_price", wh_map[wh_label])
        if st.button("Zatwierdź i zapisz sprzedaż", type="primary"):
            try:
                number = db.create_sale(
                    doc_date.isoformat(),
                    cp_map[cp_label],
                    wh_map[wh_label],
                    st.session_state.get("sale_lines", []),
                )
                st.session_state.sale_lines = []
                st.success(
                    f"Dokument {number} został zatwierdzony. Stany magazynowe zmalały, "
                    f"do kasy wpłynęło {money(total)}."
                )
                st.rerun()
            except AppError as exc:
                show_error(exc)

    with tab_journal:
        docs = db.list_sales()
        if not docs:
            st.info("Dziennik sprzedaży jest pusty.")
            return
        view = pd.DataFrame(docs)[
            ["number", "doc_date", "counterparty", "warehouse", "total"]
        ].rename(
            columns={
                "number": "Numer",
                "doc_date": "Data",
                "counterparty": "Kontrahent",
                "warehouse": "Magazyn",
                "total": "Wartość (zł)",
            }
        )
        event = st.dataframe(
            view,
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key="sales_journal",
        )
        picked = selected_id_from_df(event, docs)
        if not picked:
            st.caption("Zaznacz dokument w tabeli, aby zobaczyć szczegóły.")
            return
        doc = db.get_sale(picked)
        if not doc:
            st.error("Nie znaleziono dokumentu.")
            return
        render_document_view(doc, "sale")
        if st.button(
            "Usuń dokument sprzedaży (storno)", type="secondary", key="del_sale"
        ):
            try:
                db.delete_sale(picked)
                st.success("Dokument usunięty, stany i kasa zostały przeliczone.")
                st.rerun()
            except AppError as exc:
                show_error(exc)


def _print_label_frame(png_bytes: bytes, code: str) -> None:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    html = f"""
    <html>
    <head>
      <style>
        @page {{
          size: 100mm 150mm;
          margin: 0;
        }}
        html, body {{
          margin: 0;
          padding: 0;
          width: 100mm;
          height: 150mm;
          background: #f8fafc;
          font-family: sans-serif;
          overflow: hidden;
        }}
        .wrap {{
          padding: 12px;
          box-sizing: border-box;
          text-align: center;
        }}
        button {{
          background: #000000;
          color: #ffffff;
          border: 0;
          border-radius: 6px;
          padding: 10px 18px;
          font-weight: 700;
          cursor: pointer;
          margin-bottom: 12px;
          font-size: 15px;
        }}
        button:hover {{ background: #333333; }}
        img {{
          width: 100%;
          max-width: 100mm;
          height: auto;
          background: #fff;
          box-shadow: 0 4px 16px rgba(0,0,0,.12);
          border: 1px solid #1e293b;
          box-sizing: border-box;
        }}
        @media print {{
          html, body {{
            background: #fff;
            width: 100mm;
            height: 150mm;
          }}
          .wrap {{
            padding: 0 !important;
            margin: 0 !important;
            background: #fff;
          }}
          button {{
            display: none !important;
          }}
          img {{
            width: 100mm !important;
            height: 150mm !important;
            box-shadow: none !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
            position: relative;
            top: -2mm;
          }}
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <button onclick="window.print()">🖨️ Drukuj etykietę {code} (100 × 150 mm)</button><br>
        <img src="data:image/png;base64,{b64}" alt="Etykieta {code}">
      </div>
    </body>
    </html>
    """
    components.html(html, height=720, scrolling=False)

def page_labels() -> None:
    st.subheader("Etykiety palet")
    st.markdown(
        '<div class="hint">Towar wybierasz dowolnie ze słownika — bez powiązania ze stanem magazynowym. '
        "Każda wydrukowana etykieta dostaje unikalny kod 000001, 000002… w kodzie kreskowym Code128. "
        "Format wydruku: 100 × 150 mm.</div>",
        unsafe_allow_html=True,
    )

    products = db.list_products()
    if not products:
        st.warning("Najpierw dodaj towar w nomenklaturze.")
        return

    tab_new, tab_journal, tab_inventory = st.tabs(
        ["Nowa etykieta", "Wydane etykiety", "Magazyn palet"]
    )
    labels_map = option_map(products, product_label)
    by_id = {p["id"]: p for p in products}

    with tab_new:
        left, right = st.columns([1, 1.05], gap="large")
        with left:
            chosen = st.selectbox("Towar *", list(labels_map.keys()), key="label_prod")
            pid = labels_map[chosen]
            net = st.number_input(
                "Masa netto (kg) *",
                min_value=0.001,
                value=1.0,
                step=1.0,
                key="label_net",
            )
            tare = st.number_input(
                "Masa tary (kg) *",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="label_tare",
            )
            gross = round(float(net) + float(tare), 3)
            register_in_inventory = st.checkbox(
                "Wprowadź do ewidencji palet",
                help=(
                    "Paleta trafi do osobnego magazynu palet. "
                    "Nie zmienia to zwykłych stanów towarów w magazynach."
                ),
            )
            st.caption(f"Masa brutto: **{kg(gross)}**  ·  następny kod: **{db.peek_next_pallet_code()}**")
            print_clicked = st.button("Drukuj etykietę 100×150 mm", type="primary")

        preview = {
            "code": db.peek_next_pallet_code(),
            "sku": by_id[pid]["sku"],
            "product": by_id[pid]["name"],
            "net_weight": float(net),
            "tare_weight": float(tare),
            "gross_weight": gross,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        if print_clicked:
            try:
                saved = db.create_pallet_label(
                    pid, float(net), float(tare), register_in_inventory
                )
                png = render_label_png(saved)
                pdf = render_label_pdf(png)
                st.session_state["last_label"] = {
                    "png": png,
                    "pdf": pdf,
                    "code": saved["code"],
                }
                message = f"Nadano kod palety {saved['code']}. Etykieta gotowa do druku."
                if register_in_inventory:
                    message += " Paleta została wprowadzona do ewidencji palet."
                st.success(message)
            except AppError as exc:
                show_error(exc)

        last = st.session_state.get("last_label")
        with right:
            st.caption("Podgląd / wydruk")
            if last:
                st.download_button(
                    f"Pobierz PDF ({last['code']})",
                    data=last["pdf"],
                    file_name=f"etykieta_{last['code']}.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
                _print_label_frame(last["png"], last["code"])
            else:
                st.image(render_label_png(preview), caption="Podgląd (kod zostanie nadany przy druku)")

    with tab_journal:
        rows = db.list_pallet_labels()
        if not rows:
            st.info("Nie wydano jeszcze żadnej etykiety.")
        else:
            view = pd.DataFrame(rows)[
                ["code", "created_at", "sku", "product", "net_weight", "tare_weight", "gross_weight", "registered_in_inventory"]
            ].rename(
                columns={
                    "code": "Kod",
                    "created_at": "Data",
                    "sku": "Indeks",
                    "product": "Towar",
                    "net_weight": "Netto (kg)",
                    "tare_weight": "Tara (kg)",
                    "gross_weight": "Brutto (kg)",
                    "registered_in_inventory": "W ewidencji palet",
                }
            )
            view["W ewidencji palet"] = view["W ewidencji palet"].map(
                lambda value: "Tak" if bool(value) else "Nie"
            )
            event = st.dataframe(
                view,
                hide_index=True,
                width="stretch",
                on_select="rerun",
                selection_mode="single-row",
                key="labels_journal",
            )
            picked = selected_id_from_df(event, rows)
            if not picked:
                st.caption("Zaznacz etykietę, aby wydrukować ponownie (ten sam kod).")
            else:
                doc = db.get_pallet_label(picked)
                if doc:
                    png = render_label_png(doc)
                    pdf = render_label_pdf(png)
                    st.download_button(
                        f"Pobierz PDF ({doc['code']})",
                        data=pdf,
                        file_name=f"etykieta_{doc['code']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{doc['id']}",
                    )
                    _print_label_frame(png, doc["code"])

    with tab_inventory:
        inventory = db.list_inventory_pallets()
        if not inventory:
            st.info(
                "Magazyn palet jest pusty. Przy drukowaniu zaznacz opcję "
                "„Wprowadź do ewidencji palet”."
            )
        else:
            total_net = sum(float(row["net_weight"]) for row in inventory)
            total_gross = sum(float(row["gross_weight"]) for row in inventory)
            m1, m2, m3 = st.columns(3)
            m1.metric("Palety w ewidencji", len(inventory))
            m2.metric("Łączna masa netto", kg(total_net))
            m3.metric("Łączna masa brutto", kg(total_gross))

            st.markdown("**Indywidualne palety w magazynie palet**")
            inventory_view = pd.DataFrame(inventory)[
                [
                    "code", "inventory_registered_at", "sku", "product",
                    "net_weight", "tare_weight", "gross_weight",
                ]
            ].rename(
                columns={
                    "code": "Kod palety",
                    "inventory_registered_at": "Data wprowadzenia",
                    "sku": "Indeks",
                    "product": "Towar",
                    "net_weight": "Netto (kg)",
                    "tare_weight": "Tara (kg)",
                    "gross_weight": "Brutto (kg)",
                }
            )
            st.dataframe(inventory_view, hide_index=True, width="stretch")


def page_users() -> None:
    st.subheader("Użytkownicy")
    st.caption("Tu administrator dodaje osoby mające dostęp do aplikacji. Hasła są przechowywane wyłącznie jako bezpieczne skróty.")

    users = db.list_users()
    view = pd.DataFrame(users)[["username", "is_admin", "created_at"]].rename(
        columns={"username": "Login", "is_admin": "Administrator", "created_at": "Utworzono"}
    )
    view["Administrator"] = view["Administrator"].map(lambda value: "Tak" if bool(value) else "Nie")
    st.dataframe(view, hide_index=True, width="stretch")

    add_col, password_col = st.columns(2, gap="large")
    with add_col:
        st.markdown("**Dodaj użytkownika**")
        with st.form("add_user_form", clear_on_submit=True):
            username = st.text_input("Login *", placeholder="np. magazynier")
            password = st.text_input("Hasło *", type="password")
            is_admin = st.checkbox("Administrator")
            if st.form_submit_button("Dodaj użytkownika", type="primary"):
                if len(password) < 8:
                    st.error("Hasło musi mieć co najmniej 8 znaków.")
                else:
                    try:
                        db.create_user(username, hash_password(password), is_admin)
                        st.success("Użytkownik został dodany.")
                        st.rerun()
                    except AppError as exc:
                        show_error(exc)

    with password_col:
        st.markdown("**Zmień hasło**")
        options = {user["username"]: user for user in users}
        selected_name = st.selectbox("Użytkownik", list(options))
        with st.form("change_password_form", clear_on_submit=True):
            new_password = st.text_input("Nowe hasło *", type="password")
            if st.form_submit_button("Zapisz nowe hasło"):
                if len(new_password) < 8:
                    st.error("Hasło musi mieć co najmniej 8 znaków.")
                else:
                    db.update_user_password(options[selected_name]["id"], hash_password(new_password))
                    st.success("Hasło zostało zmienione.")


def login_required() -> bool:
    if st.session_state.get("current_user"):
        return True

    st.markdown('<div class="hero"><h1>Ewidencja złomu elektrycznego</h1><p>Zaloguj się, aby otworzyć aplikację.</p></div>', unsafe_allow_html=True)
    if db.user_count() == 0:
        st.error("Aplikacja nie ma jeszcze administratora. Dodaj dane pierwszego administratora w Streamlit Secrets.")
        return False

    _, login_col, _ = st.columns([1, 1.2, 1])
    with login_col:
        with st.form("login_form"):
            username = st.text_input("Login")
            password = st.text_input("Hasło", type="password")
            if st.form_submit_button("Zaloguj się", type="primary", width="stretch"):
                user = db.get_user(username)
                if user and verify_password(password, user["password_hash"]):
                    st.session_state["current_user"] = {
                        "id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"]),
                    }
                    st.rerun()
                st.error("Nieprawidłowy login lub hasło.")
    return False


def page_reports() -> None:
    st.subheader("Raporty / Pulpit")
    totals = db.get_dashboard_totals()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Kasa (saldo)", money(totals["cash"]))
    m2.metric("Wydatki na zakupy", money(totals["purchases"]))
    m3.metric("Przychody ze sprzedaży", money(totals["sales"]))
    m4.metric("Wynik finansowy", money(totals["profit"]))

    st.divider()
    st.markdown("**Stany towarów według magazynów**")
    stock = db.get_stock_report()
    if not stock:
        st.info("Brak stanów. Zatwierdź dokument zakupu.")
        return
    view = pd.DataFrame(stock).rename(
        columns={
            "warehouse": "Magazyn",
            "sku": "Indeks",
            "product": "Towar",
            "quantity": "Ilość",
        }
    )
    st.dataframe(view, hide_index=True, width="stretch")


if not login_required():
    st.stop()


st.markdown(
    """
    <div class="hero">
      <h1>Ewidencja złomu elektrycznego</h1>
      <p>Zakupy, sprzedaż, magazyn i etykiety palet · rozliczenia w PLN</p>
    </div>
    """,
    unsafe_allow_html=True,
)

MENU = [
    "Pulpit",
    "Nomenklatura",
    "Kontrahenci",
    "Magazyny",
    "Zakupy",
    "Sprzedaż",
    "Etykiety palet",
]
if st.session_state["current_user"]["is_admin"]:
    MENU.append("Użytkownicy")

with st.sidebar:
    st.markdown("**Nawigacja**")
    page = st.radio("Sekcja", MENU, label_visibility="collapsed")
    st.divider()
    st.caption(f"Zalogowano: {st.session_state['current_user']['username']}")
    if st.button("Wyloguj się", width="stretch"):
        st.session_state.pop("current_user", None)
        st.rerun()
    st.divider()
    st.metric("Kasa", money(db.get_cash_balance()))
    st.caption(
        "Ujemna kasa oznacza, że zakupy nie zostały jeszcze pokryte sprzedażą. Waluta: złoty polski (PLN)."
    )

pages = {
    "Pulpit": page_reports,
    "Nomenklatura": page_products,
    "Kontrahenci": page_counterparties,
    "Magazyny": page_warehouses,
    "Zakupy": page_purchases,
    "Sprzedaż": page_sales,
    "Etykiety palet": page_labels,
    "Użytkownicy": page_users,
}
pages[page]()
