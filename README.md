# Ewidencja złomu elektrycznego

Lokalna aplikacja webowa do ewidencji zakupu i sprzedaży złomu elektrycznego.
Kwoty są prowadzone w **złotych polskich (PLN)**. Dane zapisują się w pliku SQLite `scrap_accounting.db` obok programu.

## Instalacja i uruchomienie

```bash
cd /Users/zurab/Documents/p_service
pip install -r requirements.txt
streamlit run app.py
```

Albo bez pliku zależności:

```bash
pip install streamlit pandas
streamlit run app.py
```

Interfejs otworzy się w przeglądarce (zwykle http://localhost:8501).

## Jak pracować

1. Uzupełnij słowniki: **Nomenklatura**, **Kontrahenci**, **Magazyny**.
2. Wystaw **Zakup** — towar wchodzi na magazyn, kwota schodzi z kasy (kasa może zejść na minus).
3. Wystaw **Sprzedaż** — towar schodzi z magazynu, pieniądze wpływają do kasy. Nie da się sprzedać więcej, niż jest na stanie.
4. Na **Pulpicie** widać kasę i stany według magazynów.

Usunięcie dokumentu w dzienniku robi storno stanów i kasy.
