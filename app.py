import streamlit as st
import pandas as pd
import pulp

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Usher Scheduler Pro", page_icon="📅", layout="wide")

# --- JUDUL & DESKRIPSI ---
st.title("🎭 Usher Scheduler for Musikal Production")

st.markdown("""
Aplikasi ini menggunakan **Integer Linear Programming** untuk menyusun jadwal secara otomatis.

**Aturan Penjadwalan:**
1. ✅ **Prioritas Flex:** Dimaksimalkan semampu mereka.
2. ⚖️ **Batasan Shift:** Jumlah shift Flex tidak boleh melebihi Shift Core terendah.
3. 🎯 **Target Harian:** Kebutuhan jumlah usher per hari wajib terpenuhi.
""")

# --- FUNGSI OPTIMASI (LOGIKA UTAMA) ---
def run_optimization(df, demand_target):
    # 1. Persiapan Data
    ushers = df['Nama'].tolist()
    roles = df['Peran'].tolist()
    
    # Ambil kolom tanggal (semua kolom setelah 'Nama' dan 'Peran')
    date_columns = df.columns[2:] 
    days = range(len(date_columns))
    
    # Identifikasi Core & Flex
    core_ushers = [u for u, r in zip(ushers, roles) if r.strip().lower() == 'core']
    flex_ushers = [u for u, r in zip(ushers, roles) if r.strip().lower() == 'flex']
    
    # Availability Matrix
    availability = []
    for _, row in df.iterrows():
        availability.append(row[date_columns].tolist())

    # 2. Setup PuLP
    prob = pulp.LpProblem("Usher_Scheduling", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("Shift", ((u, d) for u in ushers for d in days), cat='Binary')
    
    # Variabel Bantu Total Shift
    total_shifts = {u: pulp.lpSum(x[u, d] for d in days) for u in ushers}

    # 3. Objective Function (Bobot)
    # Flex = 100, Core = 1
    prob += (
        pulp.lpSum(1 * x[u, d] for u in core_ushers for d in days) + 
        pulp.lpSum(100 * x[u, d] for u in flex_ushers for d in days)
    )

    # 4. Constraints
    
    # A. Demand Harian
    for d in days:
        prob += pulp.lpSum(x[u, d] for u in ushers) == demand_target, f"Demand_Day_{d}"

    # B. Availability
    for i, u in enumerate(ushers):
        for d in days:
            prob += x[u, d] <= availability[i][d], f"Avail_{u}_{d}"

    # C. Rata-rata Flex (Pemerataan)
    if len(flex_ushers) > 0:
        num_flex = len(flex_ushers)
        sum_flex_shifts = pulp.lpSum(total_shifts[u] for u in flex_ushers)
        for u in flex_ushers:
            prob += (num_flex * total_shifts[u]) <= sum_flex_shifts + (num_flex - 1)

    # D. Ceiling Rule (Flex <= Min Core)
    for f_u in flex_ushers:
        for c_u in core_ushers:
            prob += total_shifts[f_u] <= total_shifts[c_u]

    # 5. Solve
    status = prob.solve()
    
    if pulp.LpStatus[status] != 'Optimal':
        return None, None
    
    # 6. Format Hasil ke DataFrame
    result_data = []
    for u in ushers:
        row = {'Nama': u, 'Peran': 'Core' if u in core_ushers else 'Flex'}
        total = 0
        for d_idx, d_col in enumerate(date_columns):
            val = int(pulp.value(x[u, d_idx]))
            row[d_col] = "✅" if val == 1 else "" # Pakai Centang biar cantik
            total += val
        row['Total Shift'] = total
        result_data.append(row)
        
    return pd.DataFrame(result_data), pulp.LpStatus[status]

# --- SIDEBAR (INPUT USER) ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    uploaded_file = st.file_uploader("Upload Excel Ketersediaan", type=["xlsx"])
    demand_input = st.number_input("Kebutuhan Usher per Hari", min_value=1, value=12)
    
    run_btn = st.button("🚀 Jalankan Optimasi", type="primary")

# --- AREA UTAMA ---
if uploaded_file is not None:
    # Baca Excel
    try:
        df_input = pd.read_excel(uploaded_file)
        st.write("### Data Input Preview:")
        st.dataframe(df_input.head())
        
        if run_btn:
            with st.spinner('Sedang menghitung jadwal terbaik...'):
                result_df, status = run_optimization(df_input, demand_input)
            
            if result_df is not None:
                st.success(f"Solusi Ditemukan! Status: {status}")
                
                # Tampilkan Statistik Ringkas
                col1, col2 = st.columns(2)
                avg_core = result_df[result_df['Peran']=='Core']['Total Shift'].mean()
                avg_flex = result_df[result_df['Peran']=='Flex']['Total Shift'].mean()
                
                col1.metric("Rata-rata Shift Core", f"{avg_core:.1f}")
                col2.metric("Rata-rata Shift Flex", f"{avg_flex:.1f}")

                # Tampilkan Tabel Jadwal
                st.write("### 📅 Jadwal Final")
                st.dataframe(result_df, height=500)
                
                # Tombol Download
                # Kita ubah balik icon ✅ jadi angka 1 biar mudah diolah user kalau mau didownload
                export_df = result_df.replace({"✅": 1, "": 0})
                
                # Convert ke CSV untuk download
                csv = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Jadwal (CSV)",
                    data=csv,
                    file_name="Jadwal_Usher_Final.csv",
                    mime="text/csv",
                )
                
            else:
                st.error("Solusi tidak ditemukan! Coba cek apakah ketersediaan Usher cukup untuk memenuhi kebutuhan harian.")
                
    except Exception as e:
        st.error(f"Terjadi kesalahan membaca file: {e}")
        st.info("Pastikan format Excel: Kolom 1='Nama', Kolom 2='Peran', Kolom 3 dst='Tanggal'")

else:
    st.info("👈 Silakan upload file Excel ketersediaan di menu sebelah kiri.")