import streamlit as st
import pandas as pd
import pulp
from io import BytesIO

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Usher Scheduler Pro", page_icon="📅", layout="wide")

# --- JUDUL & DESKRIPSI ---
st.title("🎭 Usher Scheduler for Musikal Production")

st.markdown("""
Aplikasi ini membantu Head of Usher menyusun jadwal shift secara otomatis menggunakan AI (Integer Linear Programming).

**Aturan Penjadwalan:**
1. ✅ **Prioritas Flex:** Dimaksimalkan semampu mereka.
2. ⚖️ **Batasan Shift:** Jumlah shift Flex tidak boleh melebihi Shift Core terendah.
3. 🎯 **Target Harian:** Kebutuhan jumlah usher per hari wajib terpenuhi.
""")

# --- PANDUAN FORMAT EXCEL (BARU!) ---
with st.expander("ℹ️ Panduan & Template Format Excel (Klik untuk Buka)"):
    st.markdown("""
    Agar aplikasi berjalan lancar, pastikan file Excel Anda memiliki kolom berikut:
    
    1. **Nama**: Nama lengkap Usher.
    2. **Peran**: Wajib diisi **'Core'** atau **'Flex'** (Huruf besar/kecil tidak masalah).
    3. **Tanggal**: Kolom selanjutnya adalah tanggal (misal: `18-Jun`, `19-Jun`, dst).
    4. **Isi Data**: Ketik **1** jika Bisa, **0** jika Tidak Bisa.
    
    **Contoh Tabel:**
    """)
    
    # Contoh Data Preview
    example_df = pd.DataFrame({
        "Nama": ["Budi (Contoh Core)", "Siti (Contoh Flex)"],
        "Peran": ["Core", "Flex"],
        "18-Jun": [1, 0],
        "19-Jun": [1, 1],
        "20-Jun": [1, 1]
    })
    st.table(example_df)
    
    # --- FITUR DOWNLOAD TEMPLATE KOSONG ---
    def get_template_byte():
        # Buat template kosong dengan header contoh
        template_df = pd.DataFrame({
            "Nama": [],
            "Peran": [],
            "Hari-1": [], "Hari-2": [], "Hari-3": []
        })
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False, sheet_name='Isi Disini')
        return output.getvalue()

    st.download_button(
        label="📥 Download Template Excel Kosong",
        data=get_template_byte(),
        file_name="Template_Jadwal_Usher.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Klik untuk mengunduh file Excel kosong yang siap diisi."
    )

# --- FUNGSI STYLE (MEWARNAI TABEL) ---
def color_schedule(val):
    color = '#d4edda' if val == '✅' else 'white'
    return f'background-color: {color}'

# --- FUNGSI OPTIMASI ---
def run_optimization(df, demand_target):
    # Bersihkan nama kolom (trim spasi)
    df.columns = df.columns.str.strip()
    
    # Validasi Kolom Wajib
    if 'Nama' not in df.columns or 'Peran' not in df.columns:
        return None, "Error: Kolom 'Nama' atau 'Peran' tidak ditemukan di Excel."

    ushers = df['Nama'].tolist()
    roles = df['Peran'].tolist()
    
    # Ambil kolom tanggal (kolom ke-3 sampai akhir)
    date_columns = df.columns[2:] 
    if len(date_columns) == 0:
        return None, "Error: Tidak ada kolom tanggal ditemukan."

    days = range(len(date_columns))
    
    # Identifikasi Core & Flex
    core_ushers = [u for u, r in zip(ushers, roles) if str(r).strip().lower() == 'core']
    flex_ushers = [u for u, r in zip(ushers, roles) if str(r).strip().lower() == 'flex']
    
    if not core_ushers: return None, "Error: Tidak ada Usher dengan peran 'Core' ditemukan."
    if not flex_ushers: return None, "Error: Tidak ada Usher dengan peran 'Flex' ditemukan."

    # Availability Matrix
    availability = []
    for _, row in df.iterrows():
        # Pastikan data availability hanya 0 atau 1
        avail_row = row[date_columns].fillna(0).astype(int).tolist()
        availability.append(avail_row)

    # Setup PuLP
    prob = pulp.LpProblem("Usher_Scheduling", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("Shift", ((u, d) for u in ushers for d in days), cat='Binary')
    total_shifts = {u: pulp.lpSum(x[u, d] for d in days) for u in ushers}

    # Objective Function
    prob += (
        pulp.lpSum(1 * x[u, d] for u in core_ushers for d in days) + 
        pulp.lpSum(100 * x[u, d] for u in flex_ushers for d in days)
    )

    # Constraints
    # 1. Demand Harian
    for d in days:
        prob += pulp.lpSum(x[u, d] for u in ushers) == demand_target
    
    # 2. Availability
    for i, u in enumerate(ushers):
        for d in days:
            prob += x[u, d] <= availability[i][d]
            
    # 3. Ceiling Rule (Flex <= Min Core)
    for f_u in flex_ushers:
        for c_u in core_ushers:
            prob += total_shifts[f_u] <= total_shifts[c_u]

    # Solve
    status = prob.solve()
    
    if pulp.LpStatus[status] != 'Optimal':
        return None, "Solusi Optimal tidak ditemukan. Cek apakah ketersediaan usher cukup untuk memenuhi kebutuhan harian."
    
    # Format Hasil
    result_data = []
    for u in ushers:
        row = {'Nama': u, 'Peran': 'Core' if u in core_ushers else 'Flex'}
        total = 0
        for d_idx, d_col in enumerate(date_columns):
            val = int(pulp.value(x[u, d_idx]))
            row[d_col] = "✅" if val == 1 else "" 
            total += val
        row['Total Shift'] = total
        result_data.append(row)
        
    return pd.DataFrame(result_data), "Optimal"

# --- FUNGSI DOWNLOAD HASIL EXCEL ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Jadwal Final')
    return output.getvalue()

# --- SIDEBAR & MAIN UI ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    uploaded_file = st.file_uploader("Upload Excel Ketersediaan", type=["xlsx"])
    demand_input = st.number_input("Kebutuhan Usher per Hari", min_value=1, value=12)
    run_btn = st.button("🚀 Jalankan Optimasi", type="primary")

if uploaded_file is not None:
    try:
        df_input = pd.read_excel(uploaded_file)
        st.write("### 📂 Data Input")
        st.dataframe(df_input.head(), height=150)
        
        if run_btn:
            with st.spinner('Sedang meracik jadwal terbaik...'):
                result_df, status_msg = run_optimization(df_input, demand_input)
            
            if result_df is not None:
                st.success(f"Berhasil! Status: {status_msg}")
                
                # Statistik
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Shift Core", int(result_df[result_df['Peran']=='Core']['Total Shift'].sum()))
                c2.metric("Total Shift Flex", int(result_df[result_df['Peran']=='Flex']['Total Shift'].sum()))
                c3.metric("Avg Shift Flex", f"{result_df[result_df['Peran']=='Flex']['Total Shift'].mean():.1f}")

                # Tabel dengan Warna
                st.write("### 📅 Jadwal Final")
                date_cols = result_df.columns[2:-1] 
                st.dataframe(result_df.style.applymap(color_schedule, subset=date_cols), height=500)
                
                # Download Hasil
                df_xlsx = to_excel(result_df)
                st.download_button(
                    label="📥 Download Hasil Jadwal (.xlsx)",
                    data=df_xlsx,
                    file_name='Jadwal_Usher_Final.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                st.error(f"Gagal: {status_msg}")
                
    except Exception as e:
        st.error(f"Terjadi kesalahan file: {e}")
else:
    st.info("👈 Silakan upload file Excel di menu sebelah kiri. Belum punya formatnya? Download template di atas 👆")
