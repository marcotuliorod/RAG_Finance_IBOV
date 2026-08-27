"""Prova executável de que a "allowlist" de tools é real: nomes fora dos 9
conhecidos nunca chegam a executar nada, mesmo que um payload de prompt
injection convença o modelo a tentar chamar algo fora do catálogo (ex.:
uma tool 'run_shell' ou 'delete_all_data' inventada). Não depende de LLM
real — testa o dispatch (generation/tools.execute_tool) diretamente com
nomes/inputs arbitrários. Ver docs/security/AI_SECURITY.md — Tool Abuse."""

from unittest.mock import MagicMock

from rag_b3.generation.tools import TOOL_SPECS, execute_tool


def test_only_nine_tools_are_ever_exposed_to_the_model():
    names = {spec["name"] for spec in TOOL_SPECS}
    assert names == {
        "ibov_latest_bar",
        "ibov_variation_between",
        "ibov_variation_last_n_trading_days",
        "ibov_extreme_between",
        "ibov_all_time_high",
        "ibov_period_summary",
        "ibov_compare_periods",
        "cvm_latest_by_feed",
        "cvm_search",
    }


def test_unknown_tool_name_never_executes_anything():
    conn = MagicMock()
    result = execute_tool(conn, "run_shell_command", {"cmd": "rm -rf /"})
    assert result == {"error": "ferramenta desconhecida: run_shell_command"}
    # Nada foi chamado no "banco" — nenhum método do mock foi tocado.
    conn.cursor.assert_not_called()


def test_unknown_tool_name_with_adversarial_input_never_executes_anything():
    # Simula um payload de prompt injection tentando invocar uma tool
    # inexistente com nome sugestivo de operação destrutiva/exfiltração.
    conn = MagicMock()
    for adversarial_name in [
        "delete_ibov_daily_history",
        "execute_sql",
        "read_env_file",
        "__import__",
        "os.system",
    ]:
        result = execute_tool(conn, adversarial_name, {})
        assert result == {"error": f"ferramenta desconhecida: {adversarial_name}"}
    conn.cursor.assert_not_called()


def test_no_tool_spec_grants_write_or_shell_or_network_capability():
    # Checagem estrutural: nenhuma descrição de tool deveria mencionar
    # escrita/execução — se uma tool assim for adicionada no futuro sem
    # atualizar este teste, ele falha e força uma revisão de segurança.
    dangerous_keywords = ["delete", "insert", "update ", "drop ", "exec", "shell", "subprocess"]
    for spec in TOOL_SPECS:
        description_lower = spec["description"].lower()
        for keyword in dangerous_keywords:
            assert keyword not in description_lower, (
                f"tool {spec['name']!r} description mentions {keyword!r} — "
                "verify this isn't a write/execute capability before allowing it"
            )
