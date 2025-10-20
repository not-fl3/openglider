import os

def get_demokite_path() -> str:
    import os
    filename = os.path.join(os.path.dirname(__file__), "common/demokite.ods")

    return filename