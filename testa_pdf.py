import os
import sys
import tempfile
import pandas as pd
from datetime import datetime

# Importa libs condicionalmente
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except Exception:
    HAS_PDFPLUMBER = False

try:
    import camelot
    HAS_CAMELOT = True
except Exception:
    HAS_CAMELOT = False

try:
    import tabula
    HAS_TABULA = True
except Exception:
    HAS_TABULA = False


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_df(df: pd.DataFrame, out_dir: str, name: str) -> str:
    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, f"{name}.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def rows_to_df(rows):
    # Converte lista de listas (pdfplumber) para DataFrame, promovendo a primeira linha a header quando possível
    if not rows or len(rows) == 0:
        return None
    # Remove colunas totalmente vazias
    cleaned = []
    for r in rows:
        if r is None:
            continue
        cleaned.append([("" if c is None else str(c).strip()) for c in r])
    if not cleaned:
        return None
    header = cleaned[0]
    data = cleaned[1:] if len(cleaned) > 1 else []
    # Se header é todo vazio, não promova
    if all(h == "" for h in header):
        # cria colunas genéricas
        cols = [f"col_{i+1}" for i in range(len(header))]
        return pd.DataFrame(cleaned, columns=cols)
    # Caso padrão
    return pd.DataFrame(data, columns=[c if c != "" else f"col_{i+1}" for i, c in enumerate(header)])


def extract_with_pdfplumber(pdf_path: str, out_dir: str):
    results = []
    if not HAS_PDFPLUMBER:
        print("pdfplumber não disponível. Pulando...")
        return results
    print("\n[PDFPlumber] Extraindo tabelas...")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Salva cabeçalho (texto) da primeira página para análise
            if len(pdf.pages) > 0:
                header_txt = pdf.pages[0].extract_text() or ""
                with open(os.path.join(out_dir, "header_page1.txt"), "w", encoding="utf-8") as f:
                    f.write(header_txt)
            total = 0
            for i, page in enumerate(pdf.pages, start=1):
                # Tente primeiro detecção padrão
                tables = page.extract_tables()
                if not tables:
                    # Tente com parâmetros finos (ajuste se necessário)
                    table_settings = {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "intersection_tolerance": 5,
                        "snap_tolerance": 3,
                        "join_tolerance": 3,
                        "edge_min_length": 3,
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1,
                    }
                    tables = page.find_tables(table_settings=table_settings).extract()
                if not tables:
                    continue
                for j, t in enumerate(tables, start=1):
                    df = rows_to_df(t)
                    if df is None or df.empty:
                        continue
                    total += 1
                    path = save_df(df, out_dir, f"pdfplumber_p{str(i).zfill(2)}_t{j}")
                    print(f"  - Página {i}, Tabela {j}: {df.shape} -> {path}")
                    results.append(df)
            print(f"[PDFPlumber] Total de tabelas extraídas: {total}")
    except Exception as e:
        print(f"[PDFPlumber] Erro: {e}")
    return results


def extract_with_camelot(pdf_path: str, out_dir: str):
    results = []
    if not HAS_CAMELOT:
        print("Camelot não disponível. Pulando...")
        return results
    print("\n[Camelot] Extraindo tabelas (lattice)...")
    try:
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
        print(f"  - Encontradas {tables.n} tabelas (lattice)")
        for idx, t in enumerate(tables, start=1):
            df = t.df
            # Promove primeira linha a header, se fizer sentido
            if len(df) > 1:
                df.columns = df.iloc[0].astype(str).str.strip()
                df = df.iloc[1:].reset_index(drop=True)
            path = save_df(df, out_dir, f"camelot_lattice_t{idx}")
            print(f"    Tabela {idx}: {df.shape} -> {path}")
            results.append(df)
    except Exception as e:
        print(f"[Camelot] lattice falhou: {e}")

    print("\n[Camelot] Extraindo tabelas (stream)...")
    try:
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
        print(f"  - Encontradas {tables.n} tabelas (stream)")
        for idx, t in enumerate(tables, start=1):
            df = t.df
            if len(df) > 1:
                df.columns = df.iloc[0].astype(str).str.strip()
                df = df.iloc[1:].reset_index(drop=True)
            path = save_df(df, out_dir, f"camelot_stream_t{idx}")
            print(f"    Tabela {idx}: {df.shape} -> {path}")
            results.append(df)
    except Exception as e:
        print(f"[Camelot] stream falhou: {e}")
    return results


def extract_with_tabula(pdf_path: str, out_dir: str):
    results = []
    if not HAS_TABULA:
        print("Tabula não disponível. Pulando...")
        return results
    print("\n[Tabula] Extraindo tabelas (lattice=True)...")
    try:
        dfs = tabula.read_pdf(pdf_path, pages="all", lattice=True, multiple_tables=True)
        print(f"  - Encontradas {len(dfs)} tabelas (lattice)")
        for idx, df in enumerate(dfs, start=1):
            path = save_df(df, out_dir, f"tabula_lattice_t{idx}")
            print(f"    Tabela {idx}: {df.shape} -> {path}")
            results.append(df)
    except Exception as e:
        print(f"[Tabula] lattice falhou: {e}")

    print("\n[Tabula] Extraindo tabelas (stream=True)...")
    try:
        dfs = tabula.read_pdf(pdf_path, pages="all", stream=True, multiple_tables=True)
        print(f"  - Encontradas {len(dfs)} tabelas (stream)")
        for idx, df in enumerate(dfs, start=1):
            path = save_df(df, out_dir, f"tabula_stream_t{idx}")
            print(f"    Tabela {idx}: {df.shape} -> {path}")
            results.append(df)
    except Exception as e:
        print(f"[Tabula] stream falhou: {e}")
    return results


def main():
    if len(sys.argv) < 2:
        pdf_path = input("Informe o caminho do PDF: ").strip('"').strip()
    else:
        pdf_path = sys.argv[1].strip('"').strip()

    if not os.path.exists(pdf_path):
        print(f"Arquivo não encontrado: {pdf_path}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("tmp", "pdf_extract", timestamp)
    ensure_dir(out_dir)

    print(f"\nArquivo: {pdf_path}")
    print(f"Saída:   {os.path.abspath(out_dir)}")
    print("\nIniciando extração...")

    extracted = []

    extracted += extract_with_pdfplumber(pdf_path, out_dir)
    extracted += extract_with_camelot(pdf_path, out_dir)
    extracted += extract_with_tabula(pdf_path, out_dir)

    # Consolidação simples: tentar concatenar tabelas com as mesmas colunas
    if extracted:
        print("\nConsolidando tabelas com colunas compatíveis...")
        # Agrupa por tupla de colunas para concatenar
        groups = {}
        for df in extracted:
            key = tuple(df.columns.tolist())
            groups.setdefault(key, []).append(df)

        consolidated_dir = os.path.join(out_dir, "consolidated")
        ensure_dir(consolidated_dir)
        for i, (cols, dfs) in enumerate(groups.items(), start=1):
            try:
                big = pd.concat(dfs, ignore_index=True)
                path = save_df(big, consolidated_dir, f"group_{i}")
                print(f"  Grupo {i} ({len(cols)} cols, {len(dfs)} tabelas): {big.shape} -> {path}")
            except Exception as e:
                print(f"  Falha ao consolidar grupo {i}: {e}")

        print("\nResumo rápido das primeiras linhas:")
        pd.set_option("display.max_columns", 50)
        pd.set_option("display.use_container_width", 200)
        for i, df in enumerate(extracted[:5], start=1):
            print(f"\n--- Tabela {i} ---")
            print(df.head(10))
    else:
        print("\nNenhuma tabela extraída. O PDF pode ser digitalizado (imagem).")
        print("Se for o caso, tente OCR com Tesseract (pytesseract) + pdf2image.")


if __name__ == "__main__":
    main()