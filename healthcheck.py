"""Sonde de sante du conteneur.

Repondre une erreur applicative (4xx) prouve que Django tourne : seul un
serveur injoignable ou en erreur 5xx doit marquer le conteneur malade.
"""
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/app/login/"

try:
    reponse = urllib.request.urlopen(URL, timeout=4)
    sys.exit(0 if reponse.status < 500 else 1)
except urllib.error.HTTPError as erreur:
    sys.exit(0 if erreur.code < 500 else 1)
except Exception as erreur:  # connexion refusee, timeout, DNS...
    print(f"Healthcheck KO : {erreur}", file=sys.stderr)
    sys.exit(1)
