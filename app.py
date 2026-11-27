import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Credit Statement Analyzer", layout="wide")
st.title("📄 Bank Statement Analyzer (Exact Column Mode - MB)")

with st.sidebar:
    bank_in = st.text_input("Bank / Branch", "Kasikornbank / Silom")
    acc_type = st.selectbox("Type", ("S/A", "C/A"))
    acc_num = st.text_input("Account No.", "012-3-45678-9")
    acc_name = st.text_input("Account Name", "ABC CO., LTD.")
    od_lim = st.number_input("OD Limit (MB)", 0.0, step=0.5)

pdf_file = st.file_uploader("Upload Digital PDF Statement", type="pdf")

if pdf_file:
    data = {}
    ret_c_amt, ret_c_cnt = 0.0, 0
    ret_a_amt, ret_a_cnt = 0.0, 0
    audit_rows = []

    m_map = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
    }
    date_re = re.compile(r"^(\d{1,2})(/|-)(\d{1,2}|[A-Za-z]{3})(/|-)(\d{2,4})$")
    num_re = re.compile(r"^-?\d[\d,]*\.\d{2}$")

    wd_x, dep_x, bal_x = None, None, None

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            # 1. ค้นหาพิกัดแกน X ของหัวคอลัมน์ (ถอน / ฝาก / ยอดคงเหลือ) จากตารางจริง
            for w in words:
                txt_w = w["text"].lower()
                x_center = (w["x0"] + w["x1"]) / 2
                if any(k in txt_w for k in ("ถอน", "withdrawal", "debit", "dr")):
                    wd_x = x_center
                elif any(k in txt_w for k in ("ฝาก", "deposit", "credit", "cr")):
                    dep_x = x_center
                elif any(k in txt_w for k in ("คงเหลือ", "balance")):
                    bal_x = x_center

            # 2. จัดกลุ่มคำตามบรรทัด (พิกัดแกน Y ใกล้เคียงกัน)
            lines_by_y = {}
            for w in words:
                y_key = round(w["top"] / 4) * 4
                lines_by_y.setdefault(y_key, []).append(w)

            for y_key in sorted(lines_by_y.keys()):
                line_words = sorted(lines_by_y[y_key], key=lambda item: item["x0"])
                full_line = " ".join(w["text"] for w in line_words)
                low_line = full_line.lower()

                # ข้ามบรรทัดยอดยกมา / ยอดยกไป / สรุปยอด
                if any(skip in low_line for skip in ("ยอดยกมา", "ยอดยกไป", "brought forward", "carried forward", "total", "รวม")):
                    continue

                # หาวันที่ในบรรทัด
                date_match = None
                for w in line_words:
                    m = date_re.match(w["text"])
                    if m:
                        date_match = m
                        break

                if not date_match:
                    continue

                mm_raw = date_match.group(3)
                mm = m_map.get(mm_raw.zfill(2), mm_raw.capitalize())
                yy = date_match.group(5)
                mk = f"{mm} 20{yy[-2:]}"

                # หาตัวเลขทศนิยม 2 ตำแหน่งพร้อมพิกัด X ในบรรทัดนี้
                num_items = []
                for w in line_words:
                    clean_num = w["text"].replace(",", "")
                    if num_re.match(clean_num):
                        x_c = (w["x0"] + w["x1"]) / 2
                        num_items.append((float(clean_num), x_c))

                if len(num_items) < 2:
                continue

            amt_val, amt_x = num_items[-2]
            bal_val, _ = num_items[-1]
            amt_abs = abs(amt_val)

            # เช็คเด้ง (Return Cheque)
            if any(k in low_line for k in ("เช็คคืน", "return", "bounce", "chq ret")):
                if any(k in low_line for k in ("เงินไม่พอ", "insufficient", "overdraft")):
                    ret_a_amt += amt_abs
                    ret_a_cnt += 1
                else:
                    ret_c_amt += amt_abs
                    ret_c_cnt += 1
                continue

            # ตัดสินใจว่าเป็นการฝากหรือถอนจากพิกัด X เทียบกับหัวคอลัมน์จริง (ไม่เดา)
            tx_type = "Unknown"
            if wd_x is not None and dep_x is not None:
                if abs(amt_x - dep_x) < abs(amt_x - wd_x):
                    tx_type = "Deposit"
                else:
                    tx_type = "Withdrawal"

            if tx_type == "Unknown":
                continue

            if mk not in data:
                data[mk] = {"dep_amt": 0.0, "dep_cnt": 0, "wd_amt": 0.0, "wd_cnt": 0, "bal": bal_val}

            if tx_type == "Deposit":
                data[mk]["dep_amt"] += amt_abs
                data[mk]["dep_cnt"] += 1
            else:
                data[mk]["wd_amt"] += amt_abs
                data[mk]["wd_cnt"] += 1

            data[mk]["bal"] = bal_val
            audit_rows.append({"Month": mk, "Type": tx_type, "Amount (THB)": amt_abs, "Balance (THB)": bal_val, "Raw": full_line})

div = 1_000_000.0
c1, c2 = st.columns(2)
c1.markdown(f"**Bank / Branch:** {bank_in}\n\n**Account Name:** {acc_name}")
c2.markdown(f"**Account:** {acc_type} {acc_num}\n\n**OD Limit:** {od_lim:,.2f} MB")

if data:
    last_6_months = list(data.keys())[-6:]
    rows = []
    for k in last_6_months:
        v = data[k]
        rows.append({
            "Month": k,
            "Deposit (MB)": round(v["dep_amt"] / div, 2),
            "No. Deposit": v["dep_cnt"],
            "Withdrawal (MB)": round(v["wd_amt"] / div, 2),
            "No. Withdrawal": v["wd_cnt"],
            "Ending Balance (MB)": round(v["bal"] / div, 2)
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.error("ไม่สามารถระบุหัวคอลัมน์ ฝาก/ถอน จากไฟล์ PDF นี้ได้ กรุณาแจ้งชื่อธนาคารของ Statement ที่ใช้")

r_rows = []
if ret_c_cnt > 0:
    r_rows.append({"Side": "Customer", "Amount (MB)": round(ret_c_amt / div, 2), "Times": ret_c_cnt})
if ret_a_cnt > 0:
    r_rows.append({"Side": "Applicant", "Amount (MB)": round(ret_a_amt / div, 2), "Times": ret_a_cnt})
if r_rows:
    st.subheader("Return Cheque (MB)")
    st.dataframe(pd.DataFrame(r_rows), use_container_width=True, hide_index=True)

if audit_rows:
    with st.expander("🔍 ตรวจสอบรายการเดินบัญชีรายบรรทัด (เทียบกับ Excel)"):
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
