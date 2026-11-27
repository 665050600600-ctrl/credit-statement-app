import streamlit as st
import pypdf
import pandas as pd
import re

st.set_page_config(page_title="Statement Analyzer", layout="wide")
st.title("📄 Bank Statement Analyzer")

with st.sidebar:
    bank_in = st.text_input("Bank / Branch", "Kasikornbank / Silom")
    acc_type = st.selectbox("Type", ["S/A", "C/A"])
    acc_num = st.text_input("Account No.", "012-3-45678-9")
    acc_name = st.text_input("Account Name", "ABC CO., LTD.")
    od_lim = st.number_input("OD Limit (MB)", 0.0, step=0.5)
    unit_mb = st.checkbox("Unit in MB", False)

pdf_file = st.file_uploader("Upload PDF Statement", type=["pdf"])

if pdf_file and st.button("Analyze"):
    reader = pypdf.PdfReader(pdf_file)
    txt = "\n".join([(p.extract_text() or "") for p in reader.pages])
    if not txt.strip():
        st.error("Scanned PDF is not supported.")
        st.stop()
data, ret_c, ret_a, end_bal = {}, [0.0, 0], [0.0, 0], 0.0
m_map = {"01":"Jan","02":"Feb","03":"Mar","04":"Apr","05":"May","06":"Jun","07":"Jul","08":"Aug","09":"Sep","10":"Oct","11":"Nov","12":"Dec"}
for line in txt.splitlines():
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2}|[A-Za-z]{3})[/-](\d{2,4})", line)
    nums = re.findall(r"\d[\d\s,]*\.\d{2}", line)
    if m and len(nums) >= 2:
        mm_raw = m.group(2)
        mm = m_map.get(mm_raw.zfill(2), mm_raw.capitalize())
        mk = f"{mm} 20{m.group(3)[-2:]}"
        amt = float(nums[-2].replace(",","").replace(" ",""))
        end_bal = float(nums[-1].replace(",","").replace(" ",""))
        low = line.lower()
        if any(w in low for w in ["ยอดยกมา", "brought", "เช็คคืน", "return", "bounce"]):
            if any(w in low for w in ["เช็คคืน", "return", "bounce"]):
                t = ret_a if any(w in low for w in ["เงินไม่พอ", "insufficient"]) else ret_c
                t[0] += amt
                t[1] += 1
            continue
        data.setdefault(mk, [0.0, 0, 0.0, 0])
        is_in = any(w in low for w in ["เงินเข้า", "รับโอน", "dep", "cr", "in", "รับ"])
        data[mk][0 if is_in else 2] += amt
        data[mk][1 if is_in else 3] += 1
div = 1_000_000 if unit_mb else 1
u = "MB" if unit_mb else "THB"
c1, c2 = st.columns(2)
c1.markdown(f"**Bank / Branch:** {bank_in}\n\n**Account Name:** {acc_name}")
c2.markdown(f"**Account:** {acc_type} {acc_num}\n\n**OD Limit:** {od_lim:,.2f} MB")
if data:
    df = pd.DataFrame([{"Month":k, f"Credit ({u})":v[0]/div, "No. Credit":v[1], f"Debit ({u})":v[2]/div, "No. Debit":v[3]} for k,v in data.items()])
    st.dataframe(df, use_container_width=True, hide_index=True)
r_rows = []
if ret_c[1]: r_rows.append({"Side":"Customer", f"Amount ({u})":ret_c[0]/div, "Times":ret_c[1]})
if ret_a[1]: r_rows.append({"Side":"Applicant", f"Amount ({u})":ret_a[0]/div, "Times":ret_a[1]})
if r_rows:
    st.subheader("Return Cheque")
    st.dataframe(pd.DataFrame(r_rows), use_container_width=True, hide_index=True)
st.markdown(f"### Ending Balance: {end_bal/div:,.2f} {u}")
with st.expander("Debug Text"):
    st.text(txt[:2000])
