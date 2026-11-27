import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
import pandas as pd

st.set_page_config(page_title="Credit Statement Analyzer", layout="wide")

def check_password():
if "authenticated" not in st.session_state:
st.session_state.authenticated = False
if st.session_state.authenticated:
return True
st.title("🔒 Credit Statement Analyzer")
pwd = st.text_input("กรุณากรอกรหัสผ่านเข้าใช้งาน (Access Password):", type="password")
if st.button("เข้าสู่ระบบ"):
if pwd == st.secrets.get("APP_PASSWORD", "1234"):
st.session_state.authenticated = True
st.rerun()
else:
st.error("รหัสผ่านไม่ถูกต้อง")
return False

if not check_password():
st.stop()

class MonthlySummary(BaseModel):
month: str = Field(description="Month and Year in English, e.g., Jan 2026")
credit_amount: float = Field(description="Total inflow/credit amount in THB")
credit_count: int = Field(description="Number of credit transactions")
debit_amount: float = Field(description="Total outflow/debit amount in THB")
debit_count: int = Field(description="Number of debit transactions")

class ReturnCheque(BaseModel):
side: str = Field(description="Must be either 'Customer' (deposited cheque bounced) or 'Applicant' (issued cheque bounced)")
amount: float = Field(description="Total amount of returned cheques in THB")
count: int = Field(description="Number of returned cheque occurrences")

class StatementData(BaseModel):
bank_name: str = Field(description="Bank name in English, e.g., Kasikornbank")
branch_name: str = Field(description="Branch name translated/transliterated into English")
account_type: str = Field(description="Either 'S/A' (Savings) or 'C/A' (Current)")
account_number: str = Field(description="Account number")
account_name: str = Field(description="Account holder name in English")
od_limit_mb: float = Field(description="OD limit in Million Baht (MB). Put 0.0 if not found.")
monthly_data: List[MonthlySummary]
return_cheques: List[ReturnCheque] = Field(description="List of returned/bounced cheques, empty if none")
ending_balance: float = Field(description="Final ending balance at the end of the statement period in THB")

st.title("📄 Bank Statement Analyzer (Credit Summary)")

with st.sidebar:
st.header("⚙️ Settings")
manual_od = st.number_input("OD Limit Override (MB) - กรอกถ้าในไฟล์ไม่มี", min_value=0.0, value=0.0, step=0.5)
unit_mb = st.checkbox("แสดงตัวเลขในตารางเป็นหน่วยล้านบาท (MB)", value=False)

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])

if uploaded_file:
if st.button("🚀 Analyze Statement", type="primary"):
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
st.error("ไม่พบ Gemini API Key ในระบบหลังบ้าน กรุณาตั้งค่าใน Streamlit Secrets")
st.stop()
with st.spinner("Reading and analyzing PDF statement..."):
try:
client = genai.Client(api_key=api_key)
pdf_bytes = uploaded_file.read()
prompt = """
Analyze this bank statement PDF and extract all details strictly in English.
- Translate or transliterate Thai bank names, branch names, and account names into standard English.
- Classify account type as 'S/A' (ออมทรัพย์) or 'C/A' (กระแสรายวัน).
- Extract OD limit in Million Baht (MB) if shown on the header.
- Summarize monthly credit (inflow) amount & transaction count, and debit (outflow) amount & transaction count.
- Look carefully for any Returned / Bounced Cheques (เช็คคืน). Classify 'Customer' if a deposited cheque bounced (เช็คฝากเข้าคืน), or 'Applicant' if an issued cheque bounced (เช็คสั่งจ่ายคืน/เงินไม่พอจ่าย).
- Extract the final Ending Balance.
"""
response = client.models.generate_content(
model="gemini-2.5-flash",
contents=[
types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
prompt
],
config=types.GenerateContentConfig(
response_mime_type="application/json",
response_schema=StatementData,
temperature=0.1,
),
)
data = StatementData.model_validate_json(response.text)
od_display = manual_od if manual_od > 0 else data.od_limit_mb
divisor = 1_000_000 if unit_mb else 1
unit_label = "MB" if unit_mb else "THB"
st.divider()
col_left1, col_right1 = st.columns(2)
with col_left1:
st.markdown(f"**Bank / Branch:** {data.bank_name} / {data.branch_name}")
with col_right1:
st.markdown(f"**Account:** {data.account_type} {data.account_number}")
col_left2, col_right2 = st.columns(2)
with col_left2:
st.markdown(f"**Account Name:** {data.account_name}")
with col_right2:
st.markdown(f"**OD Limit:** {od_display:,.2f} MB")
st.write("")
st.subheader(f"Monthly Cash Flow Summary ({unit_label})")
df_monthly = pd.DataFrame([
{
"Month": m.month,
f"Credit ({unit_label})": m.credit_amount / divisor,
"No. of Credit": m.credit_count,
f"Debit ({unit_label})": m.debit_amount / divisor,
"No. of Debit": m.debit_count,
}
for m in data.monthly_data
])
st.dataframe(
df_monthly.style.format({
f"Credit ({unit_label})": "{:,.2f}",
f"Debit ({unit_label})": "{:,.2f}",
}),
use_container_width=True,
hide_index=True
)
if data.return_cheques and len(data.return_cheques) > 0:
st.subheader(f"⚠️ Return Cheque Summary ({unit_label})")
df_cheque = pd.DataFrame([
{
"Side": c.side,
f"Amount ({unit_label})": c.amount / divisor,
"No. of Times": c.count
}
for c in data.return_cheques
])
st.dataframe(
df_cheque.style.format({f"Amount ({unit_label})": "{:,.2f}"}),
use_container_width=True,
hide_index=True
)
st.markdown(f"### Ending Balance: {data.ending_balance / divisor:,.2f} {unit_label}")
except Exception as e:
st.error(f"Error processing file: {e}")
