import json
import re
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def _load_deepseek_config():
    try:
        from .config_api import DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
        return DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
    except Exception:
        return None, None, None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1].strip()
    try:
        return json.loads(candidate)
    except Exception:
        return None


def call_deepseek_v3_chat(
    prompt: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    if requests is None:
        return {"status": "error", "message": "requests 库未安装", "content": None}

    cfg_key, cfg_base, cfg_model = _load_deepseek_config()

    api_key = api_key or cfg_key
    api_base = api_base or cfg_base or 'https://api.siliconflow.cn/v1'
    model = model or cfg_model or 'deepseek-ai/DeepSeek-V3'

    if not api_key:
        return {"status": "error", "message": "未提供 DeepSeek API Key", "content": None}

    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content']
        return {"status": "ok", "message": "ok", "content": content}
    except Exception as e:
        return {"status": "error", "message": f"DeepSeek 调用失败: {e}", "content": None}


def judge_symbol_definitions_with_llm(
    *,
    candidate_symbols: List[str],
    formula_text: str,
    context_before: str,
    context_after: str,
    already_explained_symbols: List[str],
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    candidate_symbols = [s for s in candidate_symbols if s]
    already_explained_symbols = [s for s in already_explained_symbols if s]

    prompt = (
        "你是论文写作规范检查助手。任务：判断【公式符号】是否在给定上下文中已经给出文字说明。\n"
        "要求：只输出一个JSON对象，不要代码块，不要解释文字。\n\n"
        "判定分级（重要）：\n"
        "- 【已说明】(newly_explained_symbols)：必须是明确的定义/解释句式（论文规范写法），例如：\n"
        "  - 'where x is ...' / 'x denotes ...' / 'x represents ...'\n"
        "  - '其中 x 表示...' / '式中 x 为...' / 'x 为...'（需明确是定义说明，不是随意出现）\n"
        "- 【疑似已说明】(suspected_explained_symbols)：上下文中出现了清楚的名词短语/同位语式指代，但不属于标准定义句式，建议作者补一句规范定义。\n"
        "- 已在 earlier 说明过的符号（already_explained_symbols）不需要重复在本处说明。\n\n"
        "你将收到：候选符号列表、公式文本、公式前后段落文本、已说明符号列表。\n"
        "请输出：\n"
        "{\n"
        "  \"newly_explained_symbols\": [..],\n"
        "  \"suspected_explained_symbols\": [..],\n"
        "  \"missing_symbols\": [..],\n"
        "  \"evidence\": {\"symbol\": \"引用的原句或短语\"}\n"
        "}\n\n"
        f"candidate_symbols: {json.dumps(candidate_symbols, ensure_ascii=False)}\n"
        f"already_explained_symbols: {json.dumps(already_explained_symbols, ensure_ascii=False)}\n\n"
        f"formula_text: {formula_text}\n\n"
        f"context_before: {context_before}\n\n"
        f"context_after: {context_after}\n"
    )

    resp = call_deepseek_v3_chat(prompt, api_key=api_key, api_base=api_base, model=model)
    if resp.get('status') != 'ok':
        return {
            'status': 'error',
            'message': resp.get('message', 'unknown error'),
            'newly_explained_symbols': [],
            'missing_symbols': candidate_symbols,
            'evidence': {},
        }

    content = (resp.get('content') or '').strip()
    parsed = _extract_json_object(content)
    if not isinstance(parsed, dict):
        return {
            'status': 'error',
            'message': f'LLM未返回有效JSON: {content[:200]}',
            'newly_explained_symbols': [],
            'missing_symbols': candidate_symbols,
            'evidence': {},
        }

    newly = parsed.get('newly_explained_symbols', [])
    suspected = parsed.get('suspected_explained_symbols', [])
    missing = parsed.get('missing_symbols', [])
    evidence = parsed.get('evidence', {})

    if not isinstance(newly, list):
        newly = []
    if not isinstance(missing, list):
        missing = []
    if not isinstance(suspected, list):
        suspected = []
    if not isinstance(evidence, dict):
        evidence = {}

    newly = [s for s in newly if isinstance(s, str)]
    suspected = [s for s in suspected if isinstance(s, str)]
    missing = [s for s in missing if isinstance(s, str)]

    allowed = set(candidate_symbols)
    newly = [s for s in newly if s in allowed]
    suspected = [s for s in suspected if s in allowed and s not in newly]
    missing = [s for s in missing if s in allowed]

    return {
        'status': 'ok',
        'message': 'ok',
        'newly_explained_symbols': newly,
        'suspected_explained_symbols': suspected,
        'missing_symbols': missing,
        'evidence': {k: v for k, v in evidence.items() if k in allowed and isinstance(v, str)},
        'raw_content': content,
    }


def judge_symbol_definitions_auto_with_llm(
    *,
    formula_text: str,
    context_before: str,
    context_after: str,
    already_explained_symbols: List[str],
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    already_explained_symbols = [s for s in already_explained_symbols if isinstance(s, str) and s]

    prompt = (
        "你是论文写作规范检查助手。任务：对给定【公式】中的【符号】进行自动抽取，并判断它们是否在给定上下文中已经给出文字说明。\n"
        "要求：只输出一个JSON对象，不要代码块，不要解释文字。\n\n"
        "抽取符号规则（尽量贴合论文写作习惯）：\n"
        "- 抽取变量/参数/常量/函数记号（含上下标、希腊字母、撇号、点/双点等导数标记）。\n"
        "- 不要抽取纯数字、运算符、括号、逗号等标点。\n"
        "- 不要抽取普通英文单词/标题词（例如 Fig, Comparison, theoretical, experimental 等）。\n"
        "- 对于 c(ω)、k(ω) 这类随频率变化的系数，优先将其视为一个整体符号（例如 c(ω)）。\n"
        "\n判定分级（重要）：\n"
        "- 【已说明】(newly_explained_symbols)：必须是明确的定义/解释句式（论文规范写法），例如：\n"
        "  - 'where x is ...' / 'x denotes ...' / 'x represents ...'\n"
        "  - '其中 x 表示...' / '式中 x 为...' / 'x 为...'（需明确是定义说明，不是随意出现）\n"
        "- 【疑似已说明】(suspected_explained_symbols)：上下文中出现了清楚的名词短语/同位语式指代，但不属于标准定义句式，建议作者补一句规范定义。例如：\n"
        "  - 英文名词短语/同位语：'the ... mass m', 'mass m', 'damping coefficient c', 'stiffness k' 等\n"
        "  - 解释其它符号时顺带限定：'x_1 is the response acceleration of the vibrating mass m'（此例中 m 疑似被说明为 vibrating mass）\n"
        "  - 中文名词短语：'振动质量 m', '阻尼系数 c', '刚度 k' 等\n"
        "- 如果符号在上下文中出现了清楚的名词短语限定（如 'mass m'），但不属于标准定义句式，则把它放入 suspected_explained_symbols（并给出 evidence），而不是放入 missing_symbols。\n"
        "- 已在 earlier 说明过的符号（already_explained_symbols）不需要重复在本处说明。\n\n"
        "证据要求（非常重要）：\n"
        "- evidence 中给出的句子/短语必须来自 context_before 或 context_after 的原文（原样引用或仅做最小必要截取）。\n"
        "- evidence 必须包含该符号本身（例如符号为 b，则证据中必须出现字符 b，而不能用 both 等词替代）。\n\n"
        "- 如果你判断某个符号已说明，则 evidence 必须给出该符号对应的原文证据（不要只给其它符号的证据而漏掉它）。\n\n"
        "请输出：\n"
        "{\n"
        "  \"extracted_symbols\": [..],\n"
        "  \"newly_explained_symbols\": [..],\n"
        "  \"suspected_explained_symbols\": [..],\n"
        "  \"missing_symbols\": [..],\n"
        "  \"evidence\": {\"symbol\": \"引用的原句或短语\"}\n"
        "}\n\n"
        f"already_explained_symbols: {json.dumps(already_explained_symbols, ensure_ascii=False)}\n\n"
        f"formula_text: {formula_text}\n\n"
        f"context_before: {context_before}\n\n"
        f"context_after: {context_after}\n"
    )

    resp = call_deepseek_v3_chat(prompt, api_key=api_key, api_base=api_base, model=model)
    if resp.get('status') != 'ok':
        return {
            'status': 'error',
            'message': resp.get('message', 'unknown error'),
            'extracted_symbols': [],
            'newly_explained_symbols': [],
            'missing_symbols': [],
            'evidence': {},
        }

    content = (resp.get('content') or '').strip()
    parsed = _extract_json_object(content)
    if not isinstance(parsed, dict):
        return {
            'status': 'error',
            'message': f'LLM未返回有效JSON: {content[:200]}',
            'extracted_symbols': [],
            'newly_explained_symbols': [],
            'missing_symbols': [],
            'evidence': {},
            'raw_content': content,
        }

    extracted = parsed.get('extracted_symbols', [])
    newly = parsed.get('newly_explained_symbols', [])
    suspected = parsed.get('suspected_explained_symbols', [])
    missing = parsed.get('missing_symbols', [])
    evidence = parsed.get('evidence', {})

    if not isinstance(extracted, list):
        extracted = []
    if not isinstance(newly, list):
        newly = []
    if not isinstance(suspected, list):
        suspected = []
    if not isinstance(missing, list):
        missing = []
    if not isinstance(evidence, dict):
        evidence = {}

    extracted = [s.strip() for s in extracted if isinstance(s, str) and s.strip()]
    newly = [s.strip() for s in newly if isinstance(s, str) and s.strip()]
    suspected = [s.strip() for s in suspected if isinstance(s, str) and s.strip()]
    missing = [s.strip() for s in missing if isinstance(s, str) and s.strip()]

    formula_text_norm = (formula_text or '').strip()

    def _symbol_in_formula(sym: str) -> bool:
        if not sym or not formula_text_norm:
            return False
        if re.fullmatch(r"[A-Za-z0-9_\^\(\)\.]+", sym):
            pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(sym)}(?![A-Za-z0-9_])")
            return bool(pat.search(formula_text_norm))
        return sym in formula_text_norm

    seen = set()
    extracted_unique = []
    for s in extracted:
        if s not in seen:
            seen.add(s)
            extracted_unique.append(s)
    extracted = [s for s in extracted_unique if _symbol_in_formula(s)]

    allowed = set(extracted)
    newly = [s for s in newly if s in allowed]
    suspected = [s for s in suspected if s in allowed]
    missing = [s for s in missing if s in allowed]

    def _unique_keep_order(items: List[str]) -> List[str]:
        seen2 = set()
        out2 = []
        for it in items:
            if it not in seen2:
                seen2.add(it)
                out2.append(it)
        return out2

    newly = _unique_keep_order(newly)
    suspected = _unique_keep_order([s for s in suspected if s not in newly])
    missing = _unique_keep_order(missing)

    # Hard guard against LLM false positives:
    # a symbol can be considered "explained" only if evidence exists, evidence contains the symbol,
    # and evidence is found in provided context.
    context_all = f"{context_before or ''}\n{context_after or ''}".strip()
    context_norm = re.sub(r'\s+', ' ', context_all).strip().lower()

    def _evidence_in_context(ev: str) -> bool:
        if not ev:
            return False
        ev_norm = re.sub(r'\s+', ' ', ev).strip().lower()
        if not ev_norm or not context_norm:
            return False
        return ev_norm in context_norm

    def _evidence_contains_symbol(sym: str, ev: str) -> bool:
        if not sym or not ev:
            return False
        # For ASCII-like symbols, enforce word-boundary to avoid matching "both" as "b".
        if re.fullmatch(r"[A-Za-z0-9_\^\(\)\.]+", sym):
            pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(sym)}(?![A-Za-z0-9_])")
            return bool(pat.search(ev))
        return sym in ev

    newly_valid = []
    newly_invalid = []
    for s in newly:
        ev = evidence.get(s, '')
        if _evidence_contains_symbol(s, ev) and _evidence_in_context(ev):
            newly_valid.append(s)
        else:
            newly_invalid.append(s)

    suspected_valid = []
    for s in suspected:
        ev = evidence.get(s, '')
        if _evidence_contains_symbol(s, ev) and _evidence_in_context(ev):
            suspected_valid.append(s)

    # move invalid explained symbols into missing
    newly = newly_valid
    for s in newly_invalid:
        if s not in missing:
            missing.append(s)
        if s in evidence:
            evidence.pop(s, None)

    suspected = suspected_valid

    return {
        'status': 'ok',
        'message': 'ok',
        'extracted_symbols': extracted,
        'newly_explained_symbols': newly,
        'suspected_explained_symbols': suspected,
        'missing_symbols': missing,
        'evidence': {k: v for k, v in evidence.items() if k in allowed and isinstance(v, str)},
        'raw_content': content,
    }
