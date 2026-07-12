CVM_FEED_BASE_URL = "https://conteudo.cvm.gov.br/feed"

# Os 6 feeds institucionais/regulatórios expostos em conteudo.cvm.gov.br/feed.html
# (confirmados via HTTP real — todos HTTP 200). Escopo acordado: sinalização
# regulatória/compliance (decisões do colegiado, normas, sanções), NÃO
# notícia de mercado por empresa (fato relevante por empresa fica em outro
# sistema da CVM, Empresas.NET/IPE, fora do escopo desta fatia).
FEEDS: dict[str, str] = {
    "decisoes": f"{CVM_FEED_BASE_URL}/decisoes.xml",
    "legislacao": f"{CVM_FEED_BASE_URL}/legislacao.xml",
    "sancionadores": f"{CVM_FEED_BASE_URL}/sancionadores.xml",
    "despachos": f"{CVM_FEED_BASE_URL}/despachos.xml",
    "audiencias": f"{CVM_FEED_BASE_URL}/audiencias.xml",
    "informativos_colegiado": f"{CVM_FEED_BASE_URL}/informativos_colegiado.xml",
}
