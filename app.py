import streamlit as st
import pypdf
import pandas as pd
import re

st.set_page_config(page_title="Statement Analyzer", layout="wide")
st.title("📄 Bank Statement Analyzer (Unit: MB)")

with st.sidebar:
    bank_in = st.text_input("Bank / Branch", "Kasikornbank / Silom")
    acc_type = st.selectbox("Type", ("S/A", "C/A"))
    acc_num = st.text_input("Account No.", "012-3-45678-9")
    acc_name = st.text_input("Account Name", "ABC CO., LTD.")
    od_lim = st.number_input("OD Limit (MB)", 0.0, step=0.5)

pdf_file = st.file_uploader("Upload PDF Statement", type="pdf")

if pdf_file and st.button("Analyze"):
    reader = pypdf.PdfReader(pdf_file)
    txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    if not txt.strip():
        st.error("Scanned PDF is not supported.")
        st.stop()

    data = {}
    ret_c_amt = 0.0
    ret_c_cnt = 0
    ret_a_amt = 0.0
    ret_a_cnt = 0

    m_map = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
    }

    date_re = re.compile(r"(\d{1,2})(/|-)(\d{1,2}|[A-Za-z]{3})(/|-)(\d{2,4})")
    num_re = re.compile(r"\d[\d,]*\.\d{2}")

    for line in txt.splitlines():
        m = date_re.search(line)
        nums = num_re.findall(line)
        if m and len(nums) >= 2:
            mm_raw = m.group(3)
            mm = m_map.get(mm_raw.zfill(2), mm_raw.capitalize())
            yy = m.group(5)
            mk = f"{mm} 20{yy[-2:]}"

            amt = float(nums[-2].replace(",", ""))
            bal = float(nums[-1].replace(",", ""))
            low = line.lower()

            if any(w in low for w in ("ยอดยกมา", "brought", "เช็คคืน", "return", "bounce")):
                if any(w in low for w in ("เช็คคืน", "return", "bounce")):
                    if any(w in low for w in ("เงินไม่พอ", "insufficient")):
                        ret_a_amt += amt
                        ret_a_cnt += 1
                    else:
                        ret_c_amt += amt
                        ret_c_cnt += 1
                    continue

            if mk not in data:
                data[mk] = {"cr_amt": 0.0, "cr_cnt": 0, "dr_amt": 0.0, "dr_cnt": 0, "bal": 0.0}

            is_in = any(w in low for w in ("เงินเข้า", "รับโอน", "dep", "cr", "in", "รับ"))
            if is_in:
                data[mk]["cr_amt"] += amt
                data[mk]["cr_cnt"] += 1
            else:
                data[mk]["dr_amt"] += amt
                data[mk]["dr_cnt"] += 1
                data[mk]["bal"] = bal

div = 1_000_000.0

c1, c2 = st.columns(2)
c1.markdown(f"**Bank / Branch:** {bank_in}\n\n**Account Name:** {acc_name}")
c2.markdown(f"**Account:** {acc_type} {acc_num}\n\n**OD Limit:** {od_lim:,.2f} MB")

if data:
    rows = []
    for k, v in data.items():
        rows.append({
            "Month": k,
            "Credit (MB)": round(v["cr_amt"] / div, 2),
            "No. Credit": v["cr_cnt"],
            "Debit (MB)": round(v["dr_amt"] / div, 2),
            "No. Debit": v["dr_cnt"],
            "Ending Balance (MB)": round(v["bal"] / div, 2)
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

r_rows = []
if ret_c_cnt > 0:
    r_rows.append({"Side": "Customer", "Amount (MB)": round(ret_c_amt / div, 2), "Times": ret_c_cnt})
if ret_a_cnt > 0:
    r_rows.append({"Side": "Applicant", "Amount (MB)": round(ret_a_amt / div, 2), "Times": ret_a_cnt})
if r_rows:
    st.subheader("Return Cheque (MB)")
    st.dataframe(pd.DataFrame(r_rows), use_container_width=True, hide_index=True)

with st.expander("Debug Text"):
    st.text(txt[:2000])
