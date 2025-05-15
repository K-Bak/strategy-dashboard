import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from matplotlib.patches import Wedge
import numpy as np

# --- Indlæs og forbered data ---
import gspread
from gspread_dataframe import get_as_dataframe

# Opsætning af adgang
from google.oauth2 import service_account
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(credentials)

# Åbn ark – erstat med dit eget Sheet ID
SHEET_ID = "1qGfpJ5wTqLAFtDmKaauOXouAwMKWhIBg9bIyWPEbkzc"  # kun ID-delen fra URL
worksheet = client.open_by_key(SHEET_ID).worksheet("Mersalg")
df = get_as_dataframe(worksheet, evaluate_formulas=True)

# Fjern tomme rækker
df = df.dropna(how='all')
df = df[['Produkt', 'Pris', 'Dato for salg', 'Q2 Mål']].dropna(subset=['Produkt', 'Pris'])
df['Dato for salg'] = pd.to_datetime(df['Dato for salg'])
df['Uge'] = df['Dato for salg'].dt.isocalendar().week
df['Pris'] = pd.to_numeric(df['Pris'], errors='coerce')

# --- Produktgruppering ---
def kategoriser(produkt):
    produkt = str(produkt).lower()
    if "microsoft ads" in produkt:
        return "Microsoft Ads"
    elif "youtube" in produkt:
        return "Youtube"
    elif "leadpage" in produkt:
        return "Leadpage"
    elif any(s in produkt for s in ["sst", "server-side", "server side", "server-side tracking"]):
        return "SST"
    else:
        return "Andet"

df['Produktkategori'] = df['Produkt'].apply(kategoriser)

# --- Beregninger ---
samlet = df['Pris'].sum()
q2_maal = df['Q2 Mål'].iloc[0] if 'Q2 Mål' in df.columns else 96555
procent = samlet / q2_maal if q2_maal else 0

# --- Ugeopsætning ---
start_uge = df['Uge'].min()
slut_uge = 26  # slut på Q2
alle_uger = list(range(start_uge, slut_uge + 1))

ugevis = df.groupby('Uge')['Pris'].sum().reindex(alle_uger, fill_value=0)
ugevis.index = ugevis.index.map(lambda u: f"Uge {u}")

produkt_salg = df.groupby('Produktkategori')['Pris'].sum()

# --- Layout i Streamlit ---
st.set_page_config(page_title="Google Ads Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;margin-top:-50px;margin-bottom:-80px'>Google Ads - Q2 Mål</h1>", unsafe_allow_html=True)
from streamlit_autorefresh import st_autorefresh

# Auto-refresh hver 300 sekunder (5 min)
st_autorefresh(interval=300_000, key="datarefresh")

col1, col2 = st.columns([2, 1])

# --- Linechart med markering af nuværende uge ---
with col1:
    st.subheader(" ")
    inner_cols = st.columns([0.1, 0.8, 0.1])
    with inner_cols[1]:
        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor('none')  # fjern baggrundsfarve på selve figuren
        ax.set_facecolor('none')         # fjern baggrundsfarve på aksen
        for spine in ax.spines.values():  # fjern kantlinjer
            spine.set_visible(False)
        ugevis.plot(ax=ax, marker='o', label='Realisering', color='steelblue')

        ugentlig_maal = q2_maal / (slut_uge - start_uge + 1)
        ax.axhline(y=ugentlig_maal, color='orange', linestyle='--', label='Mål pr. uge')

        nu_uge = datetime.datetime.now().isocalendar().week
        uge_labels = list(ugevis.index)
        if f"Uge {nu_uge}" in uge_labels:
            pos = uge_labels.index(f"Uge {nu_uge}")
            ax.axvspan(pos - 0.1, pos + 0.1, color='lightblue', alpha=0.2, label='Nuværende uge')

        ax.set_xlabel("Uge")
        ax.set_ylabel("kr.")
        ax.legend()
        st.pyplot(fig)

# --- Donutgraf med gradienteffekt ---
with col2:
    st.subheader(" ")
    inner_cols = st.columns([0.2, 0.6, 0.2])
    with inner_cols[1]:
        fig2, ax2 = plt.subplots(figsize=(3, 3))
        ax2.set_xlim(-1.2, 1.2)
        ax2.set_ylim(-1.2, 1.2)
        ax2.axis('off')  # Fjern akser og ticks

        # Brug colormap til gradientfarve
        from matplotlib.colors import LinearSegmentedColormap
        gradient_cmap = LinearSegmentedColormap.from_list("custom_blue", ["#1f77b4", "#66b3ff"])
        gradient_color = gradient_cmap(0.5)

        # Tegn donut som to wedges
        wedges = [
            Wedge(center=(0, 0), r=1, theta1=90 - procent * 360, theta2=90,
                  facecolor=gradient_color, width=0.3),
            Wedge(center=(0, 0), r=1, theta1=90, theta2=450 - procent * 360,
                  facecolor="#e0e0e0", width=0.3)
        ]
        for w in wedges:
            ax2.add_patch(w)

        # Midtertekst
        ax2.text(0, 0, f"{procent*100:.2f}%", ha='center', va='center', fontsize=20)

        st.pyplot(fig2)

# --- Produkt-bokse med styling ---
st.markdown("<br>", unsafe_allow_html=True)
cols = st.columns([1.4, 1.4, 1.4, 1.4, 1.4])
produkt_rækkefølge = ["Microsoft Ads", "Leadpage", "Youtube", "SST", "Andet"]

for i, navn in enumerate(produkt_rækkefølge):
    værdi = produkt_salg.get(navn, 0)
    cols[i].markdown(f"""
    <div style="text-align:center; padding:10px; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
      <div style="font-size:18px; font-weight:bold;">{navn}</div>
      <div style="font-size:24px; font-weight:normal;">{værdi:,.0f} kr.</div>
    </div>
    """, unsafe_allow_html=True)

# --- Total og progressbar ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(f"""
<div style="text-align:center; font-size:24px; font-weight:bold; margin-bottom:10px;">
  Samlet: {samlet:,.0f} kr.
</div>
""", unsafe_allow_html=True)
progress_text = f"{samlet:,.0f} kr. / {q2_maal:,.0f} kr."
st.markdown(f"""
<div style="margin-top: 20px;">
  <div style="font-size:16px; text-align:center; margin-bottom:4px;">
    {progress_text}
  </div>
  <div style="background-color:#e0e0e0; border-radius:10px; height:30px; width:100%;">
    <div style="background: linear-gradient(90deg, #1f77b4, #66b3ff); width:{procent*100}%; height:30px; border-radius:10px;"></div>
  </div>
</div>
""", unsafe_allow_html=True)