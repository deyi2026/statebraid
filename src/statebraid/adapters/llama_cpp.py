"""Thin public-HTTP adapter for llama.cpp cache-reuse observations.

StateBraid does not own llama.cpp slot scheduling, KV residency, or physical KV
storage.  Current llama-server has no request-scoped trust namespace on its
shared prompt cache, so this adapter is deliberately single-domain and declares
only the reuse mechanics that can be verified from public completion timings.
"""

from __future__ import annotations

import json
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import request

from statebraid.backend import (
    BackendCapability,
    BackendDescriptor,
    LookupObservation,
    UnsupportedBackendCapability,
)
from statebraid.cache.namespace import DEFAULT_TRUST_DOMAIN, validate_trust_domain

LLAMA_CPP_REFERENCE_SHA = "465e49b9cea78a68b9c244ffb48d0ee24a82873d"

LLAMA_CPP_BACKEND_DESCRIPTOR = BackendDescriptor(
    name="llama.cpp",
    adapter="statebraid.adapters.llama_cpp",
    capabilities=frozenset(
        {
            BackendCapability.PREFIX_LOOKUP,
            BackendCapability.HIT_ATTRIBUTION,
            BackendCapability.GENERATION_SAFETY,
        }
    ),
    notes=(
        "Public llama-server completion timings expose the actually served/reused prompt prefix.",
        "Exact prompt reuse is generation-safe on the audited source because llama-server evaluates at least one prompt token or safely recomputes more.",
        "No namespace_isolation is declared: current shared prompt cache is token-LCP keyed without a trust namespace.",
        "No admission/residency, transaction, rollback, KV storage, or KV transport ownership is claimed.",
        f"Reference source audit: ggml-org/llama.cpp@{LLAMA_CPP_REFERENCE_SHA}.",
    ),
)


class JSONTransport(Protocol):
    def get_json(self, path: str) -> Any: ...

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Any: ...


class UrllibJSONTransport:
    """Small stdlib transport so the optional adapter has no HTTP dependency."""

    def __init__(self, base_url: str, *, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _open(self, req: request.Request) -> Any:
        with request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_json(self, path: str) -> Any:
        return self._open(request.Request(self.base_url + path, method="GET"))

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Any:
        body = json.dumps(dict(payload)).encode("utf-8")
        return self._open(
            request.Request(
                self.base_url + path,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        )


@dataclass(frozen=True)
class LlamaCppReuseHandle:
    """Opaque evidence that one llama.cpp slot reused a concrete token prefix."""

    backend_identity: str
    id_slot: int
    cache_n: int


@dataclass(frozen=True)
class LlamaCppReuseStats:
    cache_n: int
    prompt_n: int

    @classmethod
    def from_response(
        cls, response: Mapping[str, Any], *, prompt_length: int
    ) -> "LlamaCppReuseStats":
        timings = response.get("timings")
        if not isinstance(timings, Mapping):
            raise ValueError("llama.cpp response is missing timings")
        cache_n = timings.get("cache_n")
        prompt_n = timings.get("prompt_n")
        if not isinstance(cache_n, int) or isinstance(cache_n, bool):
            raise ValueError("llama.cpp timings.cache_n must be an integer")
        if not isinstance(prompt_n, int) or isinstance(prompt_n, bool):
            raise ValueError("llama.cpp timings.prompt_n must be an integer")
        if cache_n < 0 or cache_n > prompt_length:
            raise ValueError(
                f"llama.cpp cache_n {cache_n} is outside prompt length {prompt_length}"
            )
        if prompt_n < 0:
            raise ValueError("llama.cpp prompt_n must be non-negative")
        if cache_n + prompt_n != prompt_length:
            raise ValueError(
                "llama.cpp timing evidence is inconsistent with the bounded "
                f"token prompt: cache_n({cache_n}) + prompt_n({prompt_n}) != "
                f"prompt_length({prompt_length})"
            )
        return cls(cache_n=cache_n, prompt_n=prompt_n)


def llama_cpp_cache_namespace(backend_identity: str) -> tuple[str, str, str]:
    """Return the only safe cache identity exposed by the stock public server.

    Current llama.cpp prompt-cache state is shared at the server process level.
    StateBraid therefore binds the adapter to one local-default trust domain and
    deliberately does not include scheduler slot IDs in cache identity.
    """

    return ("llama.cpp", backend_identity.rstrip("/"), DEFAULT_TRUST_DOMAIN)


def normalize_llama_cpp_reuse(
    *,
    backend_identity: str,
    id_slot: int,
    prompt_tokens: Sequence[int],
    response: Mapping[str, Any],
) -> LookupObservation:
    """Convert llama-server completion timings into exact-prefix evidence."""

    tokens = tuple(int(token) for token in prompt_tokens)
    stats = LlamaCppReuseStats.from_response(response, prompt_length=len(tokens))
    payload: LlamaCppReuseHandle | None = None
    if stats.cache_n:
        payload = LlamaCppReuseHandle(
            backend_identity=backend_identity,
            id_slot=id_slot,
            cache_n=stats.cache_n,
        )
    return LookupObservation.from_backend_result(
        # llama.cpp's RAM prompt cache is server-global and may move prompt
        # state across scheduler slots. Do not misrepresent id_slot as cache
        # identity or trust isolation; keep it only in the factual payload.
        llama_cpp_cache_namespace(backend_identity),
        tokens,
        payload,
        tokens[stats.cache_n :],
    )


class LlamaCppHTTPAdapter:
    """Observe public llama-server prompt reuse on one explicitly selected slot.

    The call is execution-coupled: llama-server reports cache reuse as part of a
    completion request.  `n_predict=0` keeps the probe bounded while still
    evaluating the prompt into the backend cache.
    """

    descriptor = LLAMA_CPP_BACKEND_DESCRIPTOR

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        id_slot: int = 0,
        trust_domain: str = DEFAULT_TRUST_DOMAIN,
        timeout: float = 30.0,
        transport: JSONTransport | None = None,
    ):
        if id_slot < 0:
            raise ValueError("llama.cpp id_slot must be non-negative")
        self.base_url = base_url.rstrip("/")
        self.id_slot = id_slot
        self.backend_identity = self.base_url
        self.trust_domain = validate_trust_domain(trust_domain)
        if self.trust_domain != DEFAULT_TRUST_DOMAIN:
            raise UnsupportedBackendCapability(
                "current llama.cpp public prompt cache has no request-scoped trust "
                "namespace; only local-default single-domain observation is safe"
            )
        self.namespace = llama_cpp_cache_namespace(self.backend_identity)
        self.transport = transport or UrllibJSONTransport(
            self.base_url, timeout=timeout
        )

    def _require_namespace(self, namespace: Hashable) -> None:
        if namespace != self.namespace:
            raise UnsupportedBackendCapability(
                "llama.cpp adapter is bound to one server-global local-default "
                "cache identity; alternate namespaces are unsupported"
            )

    def slots(self) -> list[Mapping[str, Any]]:
        payload = self.transport.get_json("/slots")
        if not isinstance(payload, list) or not all(
            isinstance(item, Mapping) for item in payload
        ):
            raise ValueError("llama.cpp /slots did not return a slot list")
        return payload

    def _require_exact_slot(self) -> None:
        # llama.cpp currently wraps out-of-range id_slot values modulo n_slots.
        # StateBraid rejects that ambiguity and requires the requested ID itself.
        slot_ids = {
            item.get("id")
            for item in self.slots()
            if isinstance(item.get("id"), int)
            and not isinstance(item.get("id"), bool)
        }
        if self.id_slot not in slot_ids:
            raise ValueError(
                f"llama.cpp id_slot {self.id_slot} is not present in /slots; "
                "refusing upstream modulo slot wrapping"
            )

    def lookup(
        self,
        namespace: Hashable,
        tokens: Sequence[int],
    ) -> LookupObservation:
        self._require_namespace(namespace)
        self._require_exact_slot()
        prompt_tokens = [int(token) for token in tokens]
        if not prompt_tokens:
            raise ValueError("llama.cpp reuse observation requires a non-empty prompt")
        response = self.transport.post_json(
            "/completion",
            {
                "prompt": prompt_tokens,
                "id_slot": self.id_slot,
                "cache_prompt": True,
                "n_cache_reuse": 0,
                "n_predict": 0,
                "stream": False,
            },
        )
        if not isinstance(response, Mapping):
            raise ValueError("llama.cpp /completion did not return an object")
        return normalize_llama_cpp_reuse(
            backend_identity=self.backend_identity,
            id_slot=self.id_slot,
            prompt_tokens=prompt_tokens,
            response=response,
        )

    def generation_safe_exact(
        self,
        namespace: Hashable,
        tokens: Sequence[int],
    ) -> LookupObservation:
        observation = self.lookup(namespace, tokens)
        if not observation.remaining:
            raise ValueError(
                "llama.cpp exact reuse exposed an empty generation input; "
                "the audited generation-safety invariant was not observed"
            )
        return observation


__all__ = [
    "JSONTransport",
    "LLAMA_CPP_BACKEND_DESCRIPTOR",
    "LLAMA_CPP_REFERENCE_SHA",
    "LlamaCppHTTPAdapter",
    "LlamaCppReuseHandle",
    "LlamaCppReuseStats",
    "UrllibJSONTransport",
    "llama_cpp_cache_namespace",
    "normalize_llama_cpp_reuse",
]
