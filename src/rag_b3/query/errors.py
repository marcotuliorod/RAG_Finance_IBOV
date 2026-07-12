class InsufficientDataError(Exception):
    """RF-07: não há dado histórico suficiente para responder — o chamador
    deve traduzir isso em "não tenho informação suficiente", nunca em uma
    resposta especulativa preenchida pelo LLM."""
