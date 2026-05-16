"""LLM-assisted place tagging via Azure OpenAI GPT-4.1-mini.

Used as a fallback in Stage 1 for places that rule_based_labels() assigns
no tags to.

"""
from __future__ import annotations

import json
import logging
import os
from copy import deepcopy

from ml.data.preprocess import PlaceRecord
from ml.models.place_classifier import PLACE_TAGS
from ml.utilities.cache import TTLCache

logger = logging.getLogger(__name__)

_VALID_TAGS = set(PLACE_TAGS)
_TAG_CACHE = TTLCache(
    maxsize=int(os.getenv("LLM_TAG_CACHE_MAXSIZE", "2048")),
    ttl_seconds=float(os.getenv("LLM_TAG_CACHE_TTL_SECONDS", "604800")),
)

_SYSTEM_PROMPT = f"""You are a travel-place classifier. Given a list of places,
assign each one zero or more tags from this fixed vocabulary:

{json.dumps(PLACE_TAGS, indent=2)}

Tag meanings (brief):
- food_and_drink: restaurants, cafes, bars, food markets
- nightlife: bars, clubs, late-night venues
- outdoor: parks, beaches, nature, gardens
- cultural: museums, galleries, theatres, art spaces
- historical: landmarks, heritage sites, monuments
- scenic: viewpoints, natural beauty, picturesque spots
- family_friendly: good for kids and families
- shopping: malls, boutiques, markets
- wellness: spas, fitness, yoga studios
- adventurous: hiking, climbing, extreme sports
- pet_friendly: dog-friendly venues
- romantic: date spots, intimate settings
- budget_friendly: free or very affordable
- upscale: luxury, fine dining, premium
- quick_visit: typically under 1 hour (cafes, info points)

Respond with a JSON object in this exact format:
{{"tags": [["tag1", "tag2"], ["tag3"], [], ...]}}

The outer array must have exactly one entry per input place, in the same order.
Use an empty array [] for a place that fits none of the tags.
Only use tags from the vocabulary above — no others."""


def _get_client():
    from openai import AzureOpenAI
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    key = os.getenv("AZURE_OPENAI_KEY", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    if not (endpoint and key and deployment):
        return None, None
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=key,
        api_version="2024-12-01-preview",
    )
    return client, deployment


def _place_cache_key(place: PlaceRecord) -> tuple:
    return (
        str(place.get("name", "")).strip().lower(),
        tuple(sorted(str(c).lower() for c in (place.get("categories") or []))),
        str(place.get("suburb") or place.get("district") or "").strip().lower(),
    )


def tag_untagged_places(places: list[PlaceRecord]) -> list[PlaceRecord]:
    """Run LLM tagging on any places that have an empty tags list.

    Returns the full list with LLM tags merged in for previously untagged places.
    """
    result_places = list(places)
    untagged_indices = [i for i, p in enumerate(places) if len(p.get("tags") or []) < 2]
    if not untagged_indices:
        return places

    missed_indices: list[int] = []
    cache_hits = 0
    for idx in untagged_indices:
        cached = _TAG_CACHE.get(_place_cache_key(places[idx]))
        if cached is TTLCache.missing():
            missed_indices.append(idx)
            continue
        if cached:
            result_places[idx] = {**result_places[idx], "tags": deepcopy(cached)}
        cache_hits += 1

    if cache_hits:
        logger.info("LLM tagger cache hit for %d / %d places", cache_hits, len(untagged_indices))
    if not missed_indices:
        return result_places

    client, deployment = _get_client()
    if client is None or not deployment:
        logger.debug("LLM tagger skipped")
        return result_places

    untagged_places = [places[i] for i in missed_indices]
    place_list = [
        {
            "name":       p.get("name", ""),
            "categories": p.get("categories") or [],
            "suburb":     p.get("suburb") or p.get("district") or "",
        }
        for p in untagged_places
    ]

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(place_list)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
        tags_list: list[list[str]] = result.get("tags", [])
    except Exception as e:
        logger.warning("LLM tagger failed (%s) — skipping", e)
        return result_places

    if len(tags_list) != len(missed_indices):
        logger.warning(
            "LLM tagger returned %d tag lists for %d places — skipping",
            len(tags_list), len(missed_indices),
        )
        return result_places

    llm_tagged = 0
    for idx, tags_raw in zip(missed_indices, tags_list):
        valid = [t for t in tags_raw if t in _VALID_TAGS]
        _TAG_CACHE.set(_place_cache_key(places[idx]), valid)
        if valid:
            result_places[idx] = {**result_places[idx], "tags": valid}
            llm_tagged += 1

    logger.info(
        "LLM tagger: %d / %d untagged places received tags",
        llm_tagged, len(missed_indices),
    )
    return result_places
