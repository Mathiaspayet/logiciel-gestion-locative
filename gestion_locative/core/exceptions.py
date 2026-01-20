"""
Exceptions personnalisées pour l'application de gestion locative.
"""
from datetime import date


class TarificationNotFoundError(Exception):
    """Exception levée quand aucune tarification n'est trouvée pour une date donnée."""

    def __init__(self, target_date, bail=None):
        self.target_date = target_date
        self.bail = bail

        if isinstance(target_date, date):
            date_str = target_date.strftime('%d/%m/%Y')
        else:
            date_str = str(target_date)

        message = f"Aucune tarification définie pour la date {date_str}."

        if bail:
            message += f" (Bail: {bail})"

        message += " Veuillez créer une tarification dans l'admin avant de générer ce document."

        super().__init__(message)


class InvalidPeriodError(Exception):
    """Exception levée quand une période est invalide."""

    def __init__(self, message):
        super().__init__(message)


class ContinuityError(Exception):
    """Exception levée quand il y a un trou dans les tarifications."""

    def __init__(self, bail, gaps):
        self.bail = bail
        self.gaps = gaps

        message = f"Trous détectés dans les tarifications du bail {bail}:\n"
        for gap in gaps:
            message += f"  - Entre {gap['end']} et {gap['start']}\n"

        super().__init__(message)
