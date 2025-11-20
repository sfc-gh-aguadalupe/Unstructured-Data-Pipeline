import io, os, json, time, re, concurrent.futures
import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col

# PDF rendering libraries - try multiple options
# Priority: PyMuPDF (fitz) > pypdfium2
# These enable interactive PDF preview with page navigation
PDF_RENDERER = None

try:
    # Option 1: PyMuPDF (fitz) - widely available, feature-rich
    import fitz  # PyMuPDF
    PDF_RENDERER = "fitz"
except ImportError:
    try:
        # Option 2: pypdfium2 - lightweight, good for local dev
        import pypdfium2 as pdfium
        PDF_RENDERER = "pdfium"
    except ImportError:
        # No PDF renderer available - use text fallback
        PDF_RENDERER = None

# App config & session
st.set_page_config(page_title="Snowflake Document AI", layout="wide")
session = get_active_session()

# Debug: Show PDF renderer status in sidebar (can be removed later)
if PDF_RENDERER:
    st.sidebar.success(f"PDF Preview: ✅ {PDF_RENDERER}")
else:
    st.sidebar.info("PDF Preview: Text only")

# ─────────────────────────────────────────────────────────────
# Prerequisites (schema objects)
# ─────────────────────────────────────────────────────────────
def ensure_tables():
    session.sql("""
        CREATE TABLE IF NOT EXISTS CLASS_PROMPTS (
          class_name STRING PRIMARY KEY,
          prompts VARIANT
        );
    """).collect()
    session.sql("""
        CREATE TABLE IF NOT EXISTS DOCUMENTS_PROCESSED (
          file_url STRING,
          file_ref STRING,
          class_name STRING,
          extraction_result VARIANT
        );
    """).collect()
    session.sql("""
        CREATE TABLE IF NOT EXISTS DOCUMENTS_EXTRACTED_FIELDS (
          file_url STRING,
          file_ref STRING,
          class_name STRING,
          field_name STRING,
          field_value VARIANT,
          confidence FLOAT
        );
    """).collect()
    session.sql("""
        CREATE TABLE IF NOT EXISTS NEW_UPLOADS (
          file_name STRING PRIMARY KEY,
          file_ref STRING,
          stage_name STRING,
          processed BOOLEAN DEFAULT FALSE
        );
    """).collect()
    session.sql("""
        CREATE TABLE IF NOT EXISTS DOCUMENT_OCR (
          file_name STRING PRIMARY KEY,
          file_ref STRING,
          OCR VARIANT,
          SUMMARY VARCHAR
        );
    """).collect()

# Auto-create tables on startup if they don't exist
ensure_tables()

# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────
def q(s: str) -> str:
    return (s or "").replace("'", "''")

@st.cache_data(show_spinner=False, ttl=30)
def current_context():
    row = session.sql("""
        SELECT CURRENT_ROLE() AS ROLE,
               CURRENT_DATABASE() AS DB,
               CURRENT_SCHEMA() AS SC
    """).to_pandas().iloc[0]
    return {"role": row["ROLE"], "db": row["DB"], "schema": row["SC"]}

def _collect_stage_names(df):
    out = set()
    if df is None or df.empty: return out
    cols = {c.lower(): c for c in df.columns}
    c_name, c_db, c_schema = cols.get("name"), cols.get("database_name"), cols.get("schema_name")
    for _, r in df.iterrows():
        if c_name and c_db and c_schema:
            out.add(f"{r[c_db]}.{r[c_schema]}.{r[c_name]}")
    return out

@st.cache_data(show_spinner=False, ttl=60)
def list_stages_uncached():
    stages = set()
    try:
        ctx = current_context()
        if ctx["db"] and ctx["schema"]:
            df = session.sql(f"SHOW STAGES IN SCHEMA {ctx['db']}.{ctx['schema']}").to_pandas()
            stages |= _collect_stage_names(df)
        if ctx["db"]:
            df = session.sql(f"SHOW STAGES IN DATABASE {ctx['db']}").to_pandas()
            stages |= _collect_stage_names(df)
        try:
            df = session.sql("SHOW STAGES IN ACCOUNT").to_pandas()
            stages |= _collect_stage_names(df)
        except Exception:
            pass
        try:
            df_seen = session.sql("SELECT DISTINCT stage_name FROM NEW_UPLOADS").to_pandas()
            for s in df_seen["STAGE_NAME"].dropna().tolist():
                s = s[1:] if s.startswith("@") else s
                if s: stages.add(s)
        except Exception:
            pass
    except Exception:
        pass
    return sorted(stages)

@st.cache_data(show_spinner=False, ttl=30)
def list_stage_files(stage_qualified: str) -> pd.DataFrame:
    try:
        return session.sql(f"SELECT RELATIVE_PATH, FILE_URL FROM DIRECTORY(@{stage_qualified})").to_pandas()
    except Exception as e:
        st.error(f"Could not list @{stage_qualified}: {e}")
        return pd.DataFrame(columns=["RELATIVE_PATH","FILE_URL"])

@st.cache_data(show_spinner=False)
def load_classes_df() -> pd.DataFrame:
    try:
        return session.sql("SELECT CLASS_NAME, PROMPTS FROM CLASS_PROMPTS ORDER BY CLASS_NAME").to_pandas()
    except Exception:
        return pd.DataFrame(columns=["CLASS_NAME","PROMPTS"])

def load_prompts_obj(class_name: str):
    if not class_name: return {}
    try:
        df = session.sql(f"SELECT PROMPTS FROM CLASS_PROMPTS WHERE CLASS_NAME = '{q(class_name)}'").to_pandas()
        if df.empty: return {}
        raw = df.iloc[0]["PROMPTS"]
        if isinstance(raw, (dict, list)): return raw
        return json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        return {}

# Prompt normalization: keep either {field:question} OR ['q','...']
def canonicalize_for_storage(prompts_obj, class_name=None):
    if isinstance(prompts_obj, list):
        return prompts_obj
    flat = {}
    if isinstance(prompts_obj, dict):
        if len(prompts_obj) == 1 and class_name and class_name in prompts_obj:
            v = prompts_obj[class_name]
            if isinstance(v, dict):
                for kk in ("question","prompt","q","text"):
                    if kk in v and isinstance(v[kk], str) and v[kk].strip():
                        return ['q', v[kk].strip()]
        for k, v in prompts_obj.items():
            if isinstance(v, str) and v.strip(): flat[k] = v.strip()
            elif isinstance(v, dict):
                for kk in ("question","prompt","q","text"):
                    if kk in v and isinstance(v[kk], str) and v[kk].strip():
                        flat[k] = v[kk].strip(); break
        if flat: return flat
    return ['q', f"Extract key facts for class {class_name or ''}."]

def normalize_for_extract(prompts_obj, class_name=None):
    return canonicalize_for_storage(prompts_obj, class_name)

def save_prompts(class_name: str, prompts_obj):
    canon = canonicalize_for_storage(prompts_obj, class_name)
    pj = q(json.dumps(canon, separators=(',',':')))
    session.sql(f"""
        MERGE INTO CLASS_PROMPTS t
        USING (SELECT '{q(class_name)}' AS class_name, PARSE_JSON('{pj}') AS prompts) s
        ON t.class_name = s.class_name
        WHEN MATCHED THEN UPDATE SET prompts = s.prompts
        WHEN NOT MATCHED THEN INSERT (class_name, prompts) VALUES (s.class_name, s.prompts)
    """).collect()
    load_classes_df.clear()

def delete_class(class_name: str):
    session.sql(f"DELETE FROM CLASS_PROMPTS WHERE class_name = '{q(class_name)}'").collect()
    load_classes_df.clear()

# Cortex calls
def ai_extract(stage_qualified: str, rel_path: str, prompts_obj) -> dict:
    pj = q(json.dumps(normalize_for_extract(prompts_obj), separators=(',',':')))
    r = session.sql(f"""
        SELECT AI_EXTRACT(
          file => TO_FILE('@{stage_qualified}', '{q(rel_path)}'),
          responseFormat => PARSE_JSON('{pj}')
        ) AS R
    """).to_pandas().at[0,"R"]
    return json.loads(r) if isinstance(r,str) else r

def parse_document(stage_qualified: str, rel_path: str) -> str:
    return session.sql(f"""
        SELECT TO_VARCHAR(SNOWFLAKE.CORTEX.PARSE_DOCUMENT('@{stage_qualified}', '{q(rel_path)}', {{'mode':'layout'}})) AS OCR
    """).to_pandas().at[0,"OCR"]

def summarize_text(text: str) -> str:
    prompt = f"Summarize what this document is and the key facts in 2–3 sentences.\n\n---\n{text[:6000]}".replace("'", "''")
    r = session.sql(f"SELECT AI_COMPLETE(model => 'mistral-7b', prompt => '{prompt}') AS S").to_pandas().at[0,"S"]
    return r if isinstance(r,str) else json.dumps(r)

# ─────────────────────────────────────────────────────────────
# Rendering helpers
# ─────────────────────────────────────────────────────────────
USE_BASIC_RENDERER = True

def stringify(v):
    if v is None: return ""
    if isinstance(v, (list, dict)):
        try: return json.dumps(v, ensure_ascii=False)
        except Exception: return str(v)
    if isinstance(v, (bytes, bytearray)): return f"<{len(v)} bytes>"
    return str(v)

def to_display_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.map(stringify).fillna("") if not df.empty else df

def show_table(df: pd.DataFrame, *, height: int = 420, placeholder=None):
    safe = to_display_df(df)
    target = placeholder if placeholder is not None else st
    if USE_BASIC_RENDERER:
        html = safe.to_html(index=False, escape=False)
        css = """
        <style>
          .idp-wrap {overflow:auto; max-height: %dpx; border:1px solid #eee; border-radius:8px;}
          .idp-wrap table {border-collapse:separate; border-spacing:0; width:max-content; min-width:100%%; table-layout:auto;}
          .idp-wrap th, .idp-wrap td {text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid #f0f0f0; white-space:pre-wrap; word-wrap:break-word;}
          .idp-wrap thead th {position:sticky; top:0; background:#fafafa; z-index:1; border-bottom:1px solid #e5e5e5;}
        </style>""" % height
        target.markdown(css + f'<div class="idp-wrap">{html}</div>', unsafe_allow_html=True)
    else:
        target.dataframe(safe, use_container_width=True, height=height)

def render_property_tiles(answers: dict):
    if not answers: st.info("No extracted properties."); return
    clean = {}
    for k, v in answers.items():
        s = stringify(v).strip()
        if s and s.lower() not in ("none","null",""): clean[k] = s
    if not clean: st.info("No extracted properties."); return
    keys = sorted(clean.keys())
    colA, colB = st.columns(2)
    for i, k in enumerate(keys):
        tgt = colA if i % 2 == 0 else colB
        v = clean[k]
        tgt.markdown(
            f"""
            <div style="padding:8px 10px;border:1px solid #eee;border-radius:8px;margin-bottom:10px">
              <div style="opacity:.65;font-size:12px">{k}</div>
              <div style="font-size:18px;font-weight:600;white-space:pre-wrap">{v}</div>
              <div style="color:#34a853;font-size:12px;margin-top:4px">↑ n/a</div>
            </div>
            """, unsafe_allow_html=True
        )

# VARIANT safety: JSON-encode complex Python values before write_pandas
def variantify(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)

# Namespaced widget keys + sidebar control blocks
def k(page: str, name: str) -> str:
    return f"{page}__{name}"

def sidebar_stage_control(page, label, stages_all, *, default_stage=""):
    sel = st.sidebar.selectbox(
        label + " (picker)",
        options=stages_all if stages_all else ["(none visible)"],
        index=0 if stages_all else 0,
        key=k(page, "stage_select"),
        help="Pick a visible stage, or type a custom one below."
    )
    sel = sel if stages_all else ""
    typed = st.sidebar.text_input(
        label + " (type freeform)",
        value=(default_stage or sel),
        key=k(page, "stage_text"),
        placeholder="DB.SCHEMA.STAGE"
    )
    typed = (typed or sel or "").strip()
    if typed.startswith("@"): typed = typed[1:]
    st.session_state[k(page, "stage_value")] = typed
    return typed

def sidebar_class_control(page, classes, *, default=None):
    idx = 0
    if default and default in classes:
        idx = classes.index(default)
    return st.sidebar.selectbox("Class", options=classes, index=idx if classes else 0, key=k(page, "class"))

def mirror_value(label: str, value: str, page: str, *, show_box: bool = False):
    if show_box:
        st.text_input(label, value=value, key=k(page, f"{label}_mirror"), disabled=True)
    else:
        st.caption(f"**{label}:** `{value}`")

# ─────────────────────────────────────────────────────────────
# Session state & sidebar navigation
# ─────────────────────────────────────────────────────────────
if "nav" not in st.session_state: st.session_state.nav = "main"
for k0, v0 in {
    "single_stage": None,
    "single_file": None,
    "single_class": None,
    "single_answers": None,
    "single_extraction": None,
    "single_prompts": None,
    "single_ocr_text": None,
    "single_summary": None,
    "batch_stream_df": None,
    "batch_sql_df": None,
}.items():
    st.session_state.setdefault(k0, v0)

st.sidebar.markdown("### Navigation")
if st.sidebar.button("Interactive", use_container_width=True):
    st.session_state.nav = "main"
if st.sidebar.button("Manage Classes", use_container_width=True):
    st.session_state.nav = "classes"
if st.sidebar.button("Batch Inference", use_container_width=True):
    st.session_state.nav = "batch"
if st.sidebar.button("History", use_container_width=True):
    st.session_state.nav = "history"

st.sidebar.markdown("---")

# ─────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────

# ========================= INTERACTIVE TAB =========================
if st.session_state.nav == "main":
    st.title("Snowflake Document AI - Automatic Extraction")
    st.caption("Upload → classify → prompt → extract + OCR/summary → persist.")

    # Sidebar controls for this page only
    stages_seen = list_stages_uncached()
    recent_stage = session.sql("SELECT COALESCE(MAX(stage_name), '') AS S FROM NEW_UPLOADS").to_pandas().at[0,"S"]
    default_stage = (recent_stage[1:] if recent_stage.startswith("@") else recent_stage) or (stages_seen[0] if stages_seen else "")
    INT_STAGE = sidebar_stage_control("int", "Target stage", stages_seen, default_stage=default_stage)
    uploaded = st.sidebar.file_uploader("Upload PDF / Image", type=["pdf","jpg","jpeg","png"], key=k("int","uploader"))

    # Body: show the chosen inputs
    mirror_value("Stage", INT_STAGE, "int")

    prev_col, run_col = st.columns([1, 2])

    # Preview
    internal_name = None
    with prev_col:
        st.subheader("🖼 Preview")
        if INT_STAGE and uploaded:
            file_name = os.path.basename(uploaded.name)
            file_bytes = uploaded.read()
            session.file.put_stream(io.BytesIO(file_bytes), f"@{INT_STAGE}/{file_name}", overwrite=True, auto_compress=False)
            internal_name = file_name  # optimistic name; we do retries on classify

            if file_name.lower().endswith((".jpg","jpeg","png")):
                st.image(file_bytes, caption=file_name, use_container_width=True)
            else:
                # PDF Preview with multiple renderer support
                if PDF_RENDERER == "fitz":
                    try:
                        # PyMuPDF rendering
                        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                        page_count = len(pdf_doc)
                        page_idx = st.slider("Page", 1, page_count, 1, key=k("int","page")) - 1
                        page = pdf_doc[page_idx]
                        # Render at 3x scale for quality
                        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                        img_bytes = pix.tobytes("png")
                        st.image(img_bytes, use_container_width=True)
                        pdf_doc.close()
                    except Exception as e:
                        st.info(f"📄 PDF uploaded: {file_name}")
                        st.caption(f"Preview not available: {str(e)}")
                elif PDF_RENDERER == "pdfium":
                    try:
                        # pypdfium2 rendering
                        pdf = pdfium.PdfDocument(io.BytesIO(file_bytes))
                        page_idx = st.slider("Page", 1, len(pdf), 1, key=k("int","page")) - 1
                        st.image(pdf[page_idx].render(scale=3).to_pil(), use_container_width=True)
                    except Exception as e:
                        st.info(f"📄 PDF uploaded: {file_name}")
                        st.caption(f"Preview not available: {str(e)}")
                else:
                    st.info(f"📄 PDF uploaded: {file_name}")
                    st.caption("PDF preview not available. Continue with processing.")
        elif not INT_STAGE:
            st.warning("Provide a stage (DB.SCHEMA.STAGE).")
        else:
            st.caption("Upload a file in the sidebar to preview it here.")

    with run_col:
        st.subheader("🚀 Run")
        tab_prog, tab_raw, tab_props, tab_ocr = st.tabs(["Progress", "Raw JSON", "Properties", "OCR"])

        if INT_STAGE and uploaded and internal_name:
            # Reset single-file state
            st.session_state.single_stage = INT_STAGE
            st.session_state.single_file = internal_name
            st.session_state.single_answers = None
            st.session_state.single_extraction = None
            st.session_state.single_prompts = None
            st.session_state.single_class = None
            st.session_state.single_ocr_text = None
            st.session_state.single_summary = None

            with tab_prog:
                bar = st.progress(0, text="Starting…")
                log = st.container()

                # OCR + summary in parallel
                def ocr_job():
                    try:
                        ocr_payload = parse_document(INT_STAGE, internal_name)
                        try:
                            content = json.loads(ocr_payload).get("content", ocr_payload)
                        except Exception:
                            content = ocr_payload
                        summ = summarize_text(content)
                        return content, summ
                    except Exception as e:
                        return f"(OCR failed: {e})", None

                pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
                ocr_future = pool.submit(ocr_job)
                log.write("• OCR + summary started in parallel…")

                # Classify with short retries (stage directory may lag)
                bar.progress(0.2, text="Classifying…")
                doc_class = None
                classify_sql = f"""
                    SELECT AI_EXTRACT(
                        file => TO_FILE('@{INT_STAGE}', '{q(internal_name)}'),
                        responseFormat => {{'document_class': 'How would you classify this document?'}}
                    ):response:document_class::STRING AS CLASS_NAME
                """
                last_error = None
                for attempt in range(1,6):  # Increased to 5 attempts
                    try:
                        doc_class = session.sql(classify_sql).to_pandas().at[0,"CLASS_NAME"]; break
                    except Exception as e:
                        last_error = str(e)
                        log.write(f"• Classify attempt {attempt} failed: {last_error}")
                        time.sleep(0.5)  # Increased wait time
                if not doc_class:
                    st.error(f"Classification failed after 5 attempts. Last error: {last_error}")
                    st.code(classify_sql, language="sql")
                    st.stop()
                st.session_state.single_class = doc_class
                log.write(f"• Classified → **{doc_class}**")

                # Ensure prompts exist (seed once)
                bar.progress(0.4, text="Ensuring prompts…")
                try:
                    session.sql(f"""
                        INSERT INTO CLASS_PROMPTS(class_name, prompts)
                        SELECT '{q(doc_class)}', PARSE_JSON(
                          AI_COMPLETE(model => 'mistral-7b',
                            prompt => $$Return a flat JSON object where each key is a field name and each value is a question relevant to extracting fields for the given document class. Document class = '{q(doc_class)}'. FORMAT example (do not deviate) = {{'name': 'What is the last name of the employee?', 'address': 'What is the address of the employee?'}}$$
                          )
                        )
                        WHERE NOT EXISTS (SELECT 1 FROM CLASS_PROMPTS WHERE class_name = '{q(doc_class)}')
                    """).collect()
                    prompts_obj = normalize_for_extract(load_prompts_obj(doc_class), doc_class)
                    st.session_state.single_prompts = prompts_obj
                    log.write("• Prompts ready")
                except Exception as e:
                    st.error(f"Failed to generate/load prompts: {e}")
                    st.stop()

                # Extract
                bar.progress(0.65, text="Extracting…")
                try:
                    res = ai_extract(INT_STAGE, internal_name, prompts_obj)
                    answers = (res or {}).get("response", {})
                    extraction_result = {"answers": answers}
                    st.session_state.single_answers = answers
                    st.session_state.single_extraction = extraction_result
                    log.write(f"• Extracted {len(answers)} fields")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")
                    answers = {}
                    st.session_state.single_answers = {}
                    st.session_state.single_extraction = {"error": str(e)}

                # Finish OCR
                bar.progress(0.85, text="Finishing OCR & summary…")
                try:
                    ocr_text, summary_text = ocr_future.result(timeout=120)
                except Exception as e:
                    ocr_text, summary_text = f"(OCR failed: {e})", None
                st.session_state.single_ocr_text = ocr_text
                st.session_state.single_summary = summary_text
                log.write("• OCR & summary complete")

                # Persist
                session.write_pandas(pd.DataFrame([{
                    "FILE_URL": f"@{INT_STAGE}/{internal_name}",
                    "FILE_REF": internal_name,
                    "CLASS_NAME": doc_class,
                    "EXTRACTION_RESULT": json.dumps(extraction_result)
                }]), "DOCUMENTS_PROCESSED", auto_create_table=False, quote_identifiers=False)

                if answers:
                    rows = [{
                        "FILE_URL": f"@{INT_STAGE}/{internal_name}",
                        "FILE_REF": internal_name,
                        "CLASS_NAME": doc_class,
                        "FIELD_NAME": kf,
                        "FIELD_VALUE": variantify(vf),   # <- VARIANT safety
                        "CONFIDENCE": None
                    } for kf, vf in answers.items()]
                    session.write_pandas(pd.DataFrame(rows), "DOCUMENTS_EXTRACTED_FIELDS", auto_create_table=False, quote_identifiers=False)

                session.write_pandas(pd.DataFrame([{
                    "FILE_NAME": internal_name,
                    "FILE_REF": f"@{INT_STAGE}/{internal_name}",
                    "OCR": variantify(st.session_state.single_ocr_text),       # <- VARIANT safety
                    "SUMMARY": st.session_state.single_summary
                }]), "DOCUMENT_OCR", auto_create_table=False, quote_identifiers=False)

                session.sql(f"""
                    MERGE INTO NEW_UPLOADS t
                    USING (SELECT '{q(internal_name)}' AS fn, '@{q(INT_STAGE)}' AS stg) s
                    ON t.file_name = s.fn
                    WHEN MATCHED THEN UPDATE SET t.file_ref = CONCAT(s.stg,'/',s.fn), t.stage_name = s.stg, t.processed = TRUE
                    WHEN NOT MATCHED THEN INSERT (file_name, file_ref, stage_name, processed) VALUES (s.fn, CONCAT(s.stg,'/',s.fn), s.stg, TRUE)
                """).collect()

                bar.progress(1.0, text="Done")
                st.success("Pipeline complete ✓")

        # Raw JSON
        with tab_raw:
            st.subheader("Raw JSON")
            if st.session_state.single_prompts: st.json(st.session_state.single_prompts)
            if st.session_state.single_extraction: st.json(st.session_state.single_extraction)
            else: st.caption("Run the pipeline first.")

        # Properties
        with tab_props:
            st.subheader("Properties")
            if st.session_state.single_answers:
                render_property_tiles(st.session_state.single_answers)
                flat_df = pd.DataFrame([{ "file": st.session_state.single_file or "",
                                          **st.session_state.single_answers }]).fillna("")
                c1, c2 = st.columns(2)
                csv_buf = io.StringIO(); flat_df.to_csv(csv_buf, index=False)
                c1.download_button("⬇️ Download CSV", csv_buf.getvalue(),
                                   file_name="single_result.csv", mime="text/csv")
                c2.download_button("⬇️ Download JSON",
                                   json.dumps(st.session_state.single_extraction, indent=2),
                                   file_name="single_result.json", mime="application/json")
            else:
                st.caption("Run the pipeline first.")

        # OCR tab
        with tab_ocr:
            st.subheader("OCR (layout mode)")
            if st.session_state.single_ocr_text:
                try:
                    parsed = json.loads(st.session_state.single_ocr_text)
                    content = parsed.get("content", st.session_state.single_ocr_text)
                except Exception:
                    content = st.session_state.single_ocr_text
                pretty = re.sub(r" {2,}", "\n", str(content).strip())
                st.text_area("Extracted OCR", value=pretty, height=260, key=k("int","ocr_view"))
                if st.session_state.single_summary:
                    st.markdown("**Summary**")
                    st.write(st.session_state.single_summary)
                c1, c2 = st.columns(2)
                c1.download_button("⬇️ Download OCR", data=str(content),
                                   file_name="single_ocr.txt", mime="text/plain", key=k("int","dl_ocr"))
                c2.download_button("⬇️ Download Summary",
                                   data=str(st.session_state.single_summary or ""),
                                   file_name="single_summary.txt", mime="text/plain", key=k("int","dl_sum"))
            else:
                st.caption("Run the pipeline first.")

# ========================= MANAGE CLASSES TAB =========================
elif st.session_state.nav == "classes":
    st.title("Manage Classes")
    st.caption("Edit the flat JSON schema for each class: `{ field_name: question }` (or `['q','...']`).")

    classes_df = load_classes_df()
    class_list = sorted(classes_df["CLASS_NAME"].tolist()) if not classes_df.empty else []

    # Sidebar controls
    mode = st.sidebar.radio("Action", ["Edit existing", "Create new"], key=k("classes","mode"))
    if mode == "Edit existing":
        selected = st.sidebar.selectbox("Class", class_list, key=k("classes","select")) if class_list else None
    else:
        selected = st.sidebar.text_input("New class name", key=k("classes","new_name"))

    # Body editor
    st.subheader("Prompts (JSON)")
    initial = load_prompts_obj(selected) if selected else {"field": "What is the field?"}
    text = st.text_area("JSON {field: question} or ['q','...']",
                        value=json.dumps(initial, indent=2),
                        height=260, key=k("classes","editor"))
    try:
        parsed_preview = json.loads(text)
        st.caption("Will be saved as:")
        st.code(json.dumps(canonicalize_for_storage(parsed_preview, selected), indent=2), language="json")
    except Exception:
        st.caption("Invalid JSON — fix before saving.")

    c1, c2 = st.columns(2)
    if c1.button("💾 Save", type="primary", disabled=not selected, key=k("classes","save")):
        try:
            save_prompts(selected, json.loads(text))
            st.success(f"Saved prompts for '{selected}'.")
        except Exception as e:
            st.error(f"Save failed: {e}")
    if c2.button("🗑️ Delete", disabled=not (mode == "Edit existing" and selected), key=k("classes","delete")):
        try:
            delete_class(selected)
            st.success(f"Deleted '{selected}'.")
        except Exception as e:
            st.error(f"Delete failed: {e}")

# =============================== HISTORY ===============================
elif st.session_state.nav == "history":
    st.title("History")
    st.caption("Browse past runs across documents and classes. Uses DOCUMENTS_PROCESSED, DOCUMENTS_EXTRACTED_FIELDS, and DOCUMENT_OCR.")

    # ── Filters (compact top row) ──────────────────────────────────────
    classes_df = load_classes_df()
    class_list = sorted(classes_df["CLASS_NAME"].tolist()) if not classes_df.empty else []

    c1, c2, c3 = st.columns([1.1, 1.1, 1.2])
    class_sel = c1.multiselect("Class filter", options=class_list, default=[])
    stage_like = c2.text_input("Stage contains", value="", placeholder="e.g. DOCS or DB.SCHEMA.STAGE").strip()
    file_like  = c3.text_input("File contains",  value="", placeholder="e.g. invoice.pdf").strip()

    # Build WHERE fragments (shared across queries)
    where_docs = []
    if class_sel:
        in_list = ",".join(f"'{q(c)}'" for c in class_sel)
        where_docs.append(f"def.CLASS_NAME IN ({in_list})")
    if stage_like:
        # match against derived STAGE safely (strip leading '@')
        where_docs.append(
            f"REGEXP_REPLACE(SPLIT_PART(COALESCE(def.FILE_URL,''), '/', 1), '^@','') ILIKE '%{q(stage_like)}%'"
        )
    if file_like:
        where_docs.append(f"LOWER(def.FILE_REF) LIKE '%{q(file_like.lower())}%'")
    WHERE_DOCS = " AND ".join(where_docs) if where_docs else "1=1"

    # ── Class summary (count distinct docs per class) ──────────────────
    # (No timestamp dependency)
    sql_summary = f"""
        WITH def AS (
          SELECT FILE_REF, CLASS_NAME
          FROM DOCUMENTS_EXTRACTED_FIELDS
        )
        SELECT CLASS_NAME, COUNT(DISTINCT FILE_REF) AS DOCS
        FROM def
        WHERE {WHERE_DOCS.replace("def.FILE_URL","''")}  -- guard if a stage filter was included
        GROUP BY CLASS_NAME
        ORDER BY DOCS DESC, CLASS_NAME
    """
    try:
        df_summary = session.sql(sql_summary).to_pandas()
    except Exception as e:
        st.error(f"Failed to load class summary: {e}")
        df_summary = pd.DataFrame(columns=["CLASS_NAME","DOCS"])

    # ── Documents list (one row per file/class) ────────────────────────
    # Derive stage safely; count fields; detect OCR; try to include PROCESSED_AT if it exists.
    # We’ll attempt a query WITH timestamp; if it fails, we fallback to a no-timestamp version.
    sql_docs_with_ts = f"""
        WITH def AS (
          SELECT FILE_URL, FILE_REF, CLASS_NAME,
                 TRY_TO_TIMESTAMP_NTZ(PROCESSED_AT) AS PROCESSED_AT
          FROM DOCUMENTS_EXTRACTED_FIELDS
        )
        SELECT
          def.FILE_REF,
          def.CLASS_NAME,
          REGEXP_REPLACE(SPLIT_PART(COALESCE(def.FILE_URL,''), '/', 1), '^@','') AS STAGE,
          COALESCE(def.PROCESSED_AT,
                   (SELECT MAX(TRY_TO_TIMESTAMP_NTZ(dp.PROCESSED_AT))
                      FROM DOCUMENTS_PROCESSED dp
                     WHERE dp.FILE_REF = def.FILE_REF AND dp.CLASS_NAME = def.CLASS_NAME)) AS PROCESSED_AT,
          (SELECT COUNT(*) FROM DOCUMENTS_EXTRACTED_FIELDS d2
            WHERE d2.FILE_REF = def.FILE_REF AND d2.CLASS_NAME = def.CLASS_NAME) AS FIELDS_EXTRACTED,
          IFF(EXISTS(SELECT 1 FROM DOCUMENT_OCR x WHERE x.FILE_REF = def.FILE_REF), TRUE, FALSE) AS HAS_OCR
        FROM def
        WHERE {WHERE_DOCS}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY def.FILE_REF, def.CLASS_NAME ORDER BY def.PROCESSED_AT DESC NULLS LAST) = 1
        ORDER BY PROCESSED_AT DESC NULLS LAST, def.FILE_REF
    """
    sql_docs_no_ts = f"""
        WITH def AS (
          SELECT FILE_URL, FILE_REF, CLASS_NAME
          FROM DOCUMENTS_EXTRACTED_FIELDS
        )
        SELECT
          def.FILE_REF,
          def.CLASS_NAME,
          REGEXP_REPLACE(SPLIT_PART(COALESCE(def.FILE_URL,''), '/', 1), '^@','') AS STAGE,
          NULL AS PROCESSED_AT,
          (SELECT COUNT(*) FROM DOCUMENTS_EXTRACTED_FIELDS d2
            WHERE d2.FILE_REF = def.FILE_REF AND d2.CLASS_NAME = def.CLASS_NAME) AS FIELDS_EXTRACTED,
          IFF(EXISTS(SELECT 1 FROM DOCUMENT_OCR x WHERE x.FILE_REF = def.FILE_REF), TRUE, FALSE) AS HAS_OCR
        FROM def
        WHERE {WHERE_DOCS}
        QUALIFY ROW_NUMBER() OVER (PARTITION BY def.FILE_REF, def.CLASS_NAME ORDER BY def.FILE_REF) = 1
        ORDER BY def.FILE_REF, def.CLASS_NAME
    """
    try:
        df_docs = session.sql(sql_docs_with_ts).to_pandas()
    except Exception:
        df_docs = session.sql(sql_docs_no_ts).to_pandas()

    # ── Field-level table (flattened; VARIANT -> string via TO_JSON) ────
    sql_fields = f"""
        SELECT
          FILE_REF,
          REGEXP_REPLACE(SPLIT_PART(COALESCE(FILE_URL,''), '/', 1), '^@','') AS STAGE,
          CLASS_NAME,
          FIELD_NAME,
          TO_JSON(FIELD_VALUE) AS FIELD_VALUE
        FROM DOCUMENTS_EXTRACTED_FIELDS def
        WHERE {WHERE_DOCS}
        ORDER BY FILE_REF, CLASS_NAME, FIELD_NAME
    """
    try:
        df_fields = session.sql(sql_fields).to_pandas()
    except Exception as e:
        st.error(f"Failed to load field-level view: {e}")
        df_fields = pd.DataFrame(columns=["FILE_REF","STAGE","CLASS_NAME","FIELD_NAME","FIELD_VALUE"])

    # ── Layout & downloads ─────────────────────────────────────────────
    st.subheader("By Class")
    show_table(df_summary, height=240)
    if not df_summary.empty:
        cdl = st.columns(2)
        buf = io.StringIO(); df_summary.to_csv(buf, index=False)
        cdl[0].download_button("⬇️ Class summary (CSV)", buf.getvalue(), file_name="history_class_summary.csv", mime="text/csv")
        cdl[1].download_button("⬇️ Class summary (JSON)",
                               json.dumps(df_summary.to_dict(orient="records"), indent=2),
                               file_name="history_class_summary.json", mime="application/json")

    st.subheader("Documents")
    show_table(df_docs, height=260)
    if not df_docs.empty:
        cdl = st.columns(2)
        buf = io.StringIO(); df_docs.to_csv(buf, index=False)
        cdl[0].download_button("⬇️ Documents (CSV)", buf.getvalue(), file_name="history_documents.csv", mime="text/csv")
        cdl[1].download_button("⬇️ Documents (JSON)",
                               json.dumps(df_docs.to_dict(orient="records"), indent=2),
                               file_name="history_documents.json", mime="application/json")

    st.subheader("Field-level Extractions")
    show_table(df_fields, height=420)
    if not df_fields.empty:
        cdl = st.columns(2)
        buf = io.StringIO(); df_fields.to_csv(buf, index=False)
        cdl[0].download_button("⬇️ Fields (CSV)", buf.getvalue(), file_name="history_fields.csv", mime="text/csv")
        cdl[1].download_button("⬇️ Fields (JSON)",
                               json.dumps(df_fields.to_dict(orient="records"), indent=2),
                               file_name="history_fields.json", mime="application/json")


# ============================ BATCH INFERENCE ============================
else:
    st.title("Batch Inference")
    st.caption("Controls are in the left sidebar. Results stream below, one row per document.")

    # Sidebar: default to "existing stage"
    stages_all = list_stages_uncached()
    default_stage = (stages_all[0] if stages_all else "")
    BATCH_STAGE = sidebar_stage_control("batch", "Stage", stages_all, default_stage=default_stage)

    # Class picker in the sidebar
    cdf = load_classes_df()
    classes = cdf["CLASS_NAME"].tolist()
    if not classes:
        st.info("Create a class first in **Manage Classes**."); st.stop()
    RUN_CLASS = sidebar_class_control("batch", classes)

    # Mode toggle
    mode = st.sidebar.radio("Mode", ["Stream per file", "Single SQL over stage"], key=k("batch","mode"))

    # Optional: upload to stream over those specific files instead of the whole stage
    files_to_upload = st.sidebar.file_uploader("Upload files (optional; streams only",
                                               type=["pdf","jpg","jpeg","png"], accept_multiple_files=True,
                                               key=k("batch","uploader"))

    # Body readouts
    colA, colB = st.columns([1,1])
    with colA: mirror_value("Stage", BATCH_STAGE, "batch")
    with colB: mirror_value("Class", RUN_CLASS, "batch")

    # Prepare prompts
    prompts_obj = normalize_for_extract(load_prompts_obj(RUN_CLASS), RUN_CLASS)

    # Placeholders
    prog = st.empty()
    table_ph = st.empty()
    st.session_state.batch_stream_df = None
    st.session_state.batch_sql_df = None

    # Buttons
    colB1, colB2 = st.columns([1,1])
    go_stream = colB1.button("▶️ Run (stream)", type="primary", key=k("batch","go_stream")) if mode == "Stream per file" else False
    go_sql    = colB2.button("⚡ Run (single SQL over stage)", key=k("batch","go_sql")) if mode == "Single SQL over stage" else False

    # Streaming implementation
    def stream_files(stage_name, file_list):
        flat_df = pd.DataFrame({"file": file_list})
        show_table(flat_df, height=420, placeholder=table_ph)
        prog.progress(0.0, text=f"Queued {len(file_list)} files…")

        last_render = [0.0]
        def maybe_render(df):
            now = time.time()
            if now - last_render[0] > 0.15:
                show_table(df, height=420, placeholder=table_ph); last_render[0] = now

        def process_one(rel_path: str):
            answers, res_obj = {}, {}
            try:
                r = ai_extract(stage_name, rel_path, prompts_obj)
                res_obj = r if isinstance(r, dict) else {}
                answers = res_obj.get("response", {}) or {}
            except Exception as e:
                res_obj = {"error": str(e)}
            # Persist best-effort
            try:
                session.write_pandas(pd.DataFrame([{
                    "FILE_URL": f"@{stage_name}/{rel_path}",
                    "FILE_REF": rel_path,
                    "CLASS_NAME": RUN_CLASS,
                    "EXTRACTION_RESULT": json.dumps(res_obj) if not isinstance(res_obj, str) else res_obj
                }]), "DOCUMENTS_PROCESSED", auto_create_table=False, quote_identifiers=False)
            except Exception: pass
            if answers:
                try:
                    rows = [{
                        "FILE_URL": f"@{stage_name}/{rel_path}",
                        "FILE_REF": rel_path,
                        "CLASS_NAME": RUN_CLASS,
                        "FIELD_NAME": k0,
                        "FIELD_VALUE": variantify(v0),   # <- VARIANT safety
                        "CONFIDENCE": None
                    } for k0, v0 in answers.items()]
                    session.write_pandas(pd.DataFrame(rows), "DOCUMENTS_EXTRACTED_FIELDS",
                                         auto_create_table=False, quote_identifiers=False)
                except Exception: pass
            return rel_path, answers

        max_workers = min(8, max(2, (os.cpu_count() or 4)))
        all_keys = set()
        current_df = flat_df.copy()
        done, total = 0, len(file_list)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(process_one, rp): rp for rp in file_list}
            for fut in concurrent.futures.as_completed(futures):
                rel, answers = fut.result()
                new_keys = set(answers.keys()) - all_keys
                if new_keys:
                    for kf in sorted(new_keys): current_df[kf] = ""
                    all_keys |= new_keys
                ridx = current_df.index[current_df["file"] == rel]
                if len(ridx) == 0:
                    current_df.loc[len(current_df)] = {"file": rel, **{k: "" for k in all_keys}}
                    ridx = current_df.index[current_df["file"] == rel]
                for kf in all_keys:
                    if kf in answers: current_df.at[ridx[0], kf] = answers[kf]
                done += 1
                prog.progress(done/total, text=f"Processed {done}/{total}")
                maybe_render(current_df.fillna(""))

        show_table(current_df.fillna(""), height=420, placeholder=table_ph)
        st.success("Streaming complete ✓")
        return current_df.fillna("")

    # Run streaming
    if go_stream:
        if not BATCH_STAGE:
            st.error("Select or type a stage."); st.stop()
        if files_to_upload:
            # Stream only uploaded names (stage must be writable)
            with st.spinner("Staging uploads…"):
                names = []
                for f in files_to_upload:
                    fb = f.read()
                    session.file.put_stream(io.BytesIO(fb), f"@{BATCH_STAGE}/{q(f.name)}", overwrite=True, auto_compress=False)
                    names.append(f.name)
                    session.sql(f"""
                        MERGE INTO NEW_UPLOADS t
                        USING (SELECT '{q(f.name)}' AS fn, '@{q(BATCH_STAGE)}' AS stg) s
                        ON t.file_name = s.fn
                        WHEN MATCHED THEN UPDATE SET t.file_ref = CONCAT(s.stg,'/',s.fn), t.stage_name = s.stg, t.processed = FALSE
                        WHEN NOT MATCHED THEN INSERT (file_name, file_ref, stage_name, processed) VALUES (s.fn, CONCAT(s.stg,'/',s.fn), s.stg, FALSE)
                    """).collect()
            st.session_state.batch_stream_df = stream_files(BATCH_STAGE, names)
        else:
            df_files = list_stage_files(BATCH_STAGE)
            if df_files.empty:
                st.warning(f"No files found in @{BATCH_STAGE}."); st.stop()
            st.session_state.batch_stream_df = stream_files(BATCH_STAGE, df_files["RELATIVE_PATH"].tolist())

        # Downloads
        if st.session_state.batch_stream_df is not None and not st.session_state.batch_stream_df.empty:
            dlc1, dlc2 = st.columns(2)
            csv_buf = io.StringIO(); st.session_state.batch_stream_df.to_csv(csv_buf, index=False)
            dlc1.download_button("⬇️ Download CSV", csv_buf.getvalue(), file_name="batch_stream_results.csv", mime="text/csv", key=k("batch","dl_csv"))
            dlc2.download_button("⬇️ Download JSON",
                                 json.dumps(st.session_state.batch_stream_df.to_dict(orient="records"), indent=2),
                                 file_name="batch_stream_results.json", mime="application/json", key=k("batch","dl_json"))

    # Single SQL sweep
    if go_sql:
        if not BATCH_STAGE:
            st.error("Select or type a stage."); st.stop()
        prompt_json = q(json.dumps(prompts_obj, separators=(',',':')))
        df = session.sql(f"""
            SELECT RELATIVE_PATH,
                   AI_EXTRACT(file => TO_FILE('@{q(BATCH_STAGE)}', RELATIVE_PATH),
                              responseFormat => PARSE_JSON('{prompt_json}')) AS AI_EXTRACT_RESULT
            FROM DIRECTORY(@{q(BATCH_STAGE)});
        """).to_pandas()
        if df.empty:
            st.warning(f"No files in @{BATCH_STAGE} or no results."); st.stop()
        rows = []
        for r in df.itertuples(index=False):
            val = r.AI_EXTRACT_RESULT
            if isinstance(val, str):
                try: val = json.loads(val)
                except Exception: val = {"response": {}}
            ans = (val or {}).get("response", {}) or {}
            rows.append({"file": r.RELATIVE_PATH, **ans})
        st.session_state.batch_sql_df = pd.DataFrame(rows).fillna("")
        show_table(st.session_state.batch_sql_df, height=420, placeholder=table_ph)
        st.success("Batch (single SQL) complete ✓")
        c1, c2 = st.columns(2)
        csv_buf = io.StringIO(); st.session_state.batch_sql_df.to_csv(csv_buf, index=False)
        c1.download_button("⬇️ Download CSV", csv_buf.getvalue(), file_name="batch_sql_results.csv", mime="text/csv", key=k("batch","dl_sql_csv"))
        c2.download_button("⬇️ Download JSON", data=json.dumps(rows, indent=2),
                           file_name="batch_sql_results.json", mime="application/json", key=k("batch","dl_sql_json"))
