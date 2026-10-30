#!/usr/bin/env python3
"""DEPRECATO: REPORT.html non si genera più (il proprietario: "è vecchio").

Il solo deliverable HTML è STATUS.html (status_page.py), che ha i grafici nel "Quadro d'insieme".
Il testo resta in REPORT.md; i grafici per i Markdown si esportano con charts_export.py (launch/charts/*.svg).
Questo file resta solo perché le vecchie chiamate non si rompano: stampa un avviso ed esce con 0.
"""
import sys

MESSAGE = "REPORT.html non si genera più: usa status_page.py (STATUS.html) e charts_export.py"


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")   # console non UTF-8: meglio una lettera storta che un errore
    except Exception:
        pass
    print(MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
