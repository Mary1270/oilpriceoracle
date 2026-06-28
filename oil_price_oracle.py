# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class OilPriceOracle(gl.Contract):
    """
    OilPriceOracle - A decentralized oil price threshold checker.

    Anyone can submit a question like "Is Brent crude oil above $80?"
    together with a live price source URL (e.g. a financial news page).
    GenLayer's validators (each running a different LLM) independently
    read the page, extract the current price, and reach consensus on
    whether the price is Above, Below, or Equal to the given threshold.
    The result is then stored permanently on-chain.

    This demonstrates three core GenLayer building blocks:
      1. gl.nondet.web.render()      -> trustless web access (reads live price data)
      2. gl.nondet.exec_prompt()     -> LLM reasoning inside a contract
      3. gl.eq_principle.strict_eq() -> Optimistic Democracy consensus

    Note: like any non-deterministic LLM output, the result is reduced
    to a single fixed word (Above / Below / Equal / Unclear) so that
    different validators running different LLMs can reliably reach
    byte-identical consensus via strict_eq.
    """

    queries: TreeMap[str, str]
    thresholds: TreeMap[str, str]
    source_urls: TreeMap[str, str]
    results: TreeMap[str, str]
    query_count: u256

    VALID_RESULTS = ("Above", "Below", "Equal", "Unclear")

    def __init__(self):
        self.query_count = u256(0)

    @gl.public.write
    def submit_query(self, oil_type: str, threshold_price: str, source_url: str) -> str:
        """
        Submit an oil price question for the validators to check.

        oil_type: e.g. "Brent crude oil" or "WTI crude oil"
        threshold_price: e.g. "80 USD per barrel"
        source_url: a live page showing the current oil price

        Returns the query_id used to look up the result later.
        """

        def nondet():
            web_data = gl.nondet.web.render(source_url, mode="text")

            prompt = f"""
            You are a neutral financial data assistant.

            Question: Is the current price of {oil_type} Above, Below,
            or Equal to {threshold_price}?

            Source content (truncated):
            \"\"\"{web_data[:3000]}\"\"\"

            Find the current price of {oil_type} in the source content
            and compare it to {threshold_price}.

            Respond with ONLY one single word, exactly one of:
            Above
            Below
            Equal
            Unclear

            Use "Unclear" only if the source does not contain a usable
            current price for {oil_type}.
            Do not add punctuation, explanation, or any other text.
            """

            raw = gl.nondet.exec_prompt(prompt, response_format="text")
            word = raw.strip().splitlines()[0].strip()

            for option in self.VALID_RESULTS:
                if option.lower() == word.lower():
                    return option
            return "Unclear"

        result = gl.eq_principle.strict_eq(nondet)

        query_id = str(int(self.query_count))

        self.queries[query_id] = oil_type
        self.thresholds[query_id] = threshold_price
        self.source_urls[query_id] = source_url
        self.results[query_id] = result

        self.query_count = u256(int(self.query_count) + 1)

        return query_id

    @gl.public.view
    def get_query(self, query_id: str) -> str:
        """
        Look up a previously submitted query and its result.
        Returns a JSON-encoded string with: oil_type, threshold, source, result.
        """
        if query_id not in self.queries:
            raise Exception("No query found with this id")
        result = {
            "oil_type": self.queries[query_id],
            "threshold": self.thresholds[query_id],
            "source": self.source_urls[query_id],
            "result": self.results[query_id],
        }
        return json.dumps(result)

    @gl.public.view
    def total_queries(self) -> int:
        """Total number of queries submitted so far."""
        return int(self.query_count)
