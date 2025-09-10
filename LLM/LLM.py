import logging
import timeit
import os
import torch
import streamlit as st
from transformers import pipeline

# Use HF_HOME instead of deprecated TRANSFORMERS_CACHE
os.environ.setdefault('HF_HOME', os.path.join(os.curdir, 'cache'))

logging.basicConfig(
    level=logging.INFO,
    filename='llm.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@st.cache_resource
def init():
    device = 0 if torch.cuda.is_available() else -1

    summarizer = pipeline(
        "summarization",
        model="sshleifer/distilbart-cnn-12-6",
        use_fast=True,
        device=device,
    )

    detector = pipeline(
        "text-classification",
        model="1aurent/distilbert-base-multilingual-cased-finetuned-email-spam",
        use_fast=True,
        device=device if device >= 0 else None,
    )

    tagger = pipeline(
        "text2text-generation",
        model="fabiochiu/t5-base-tag-generation",
        use_fast=True,
        device=device if device >= 0 else None,
    )

    return [summarizer, detector, tagger]


def summarize(prompt: str, summarizer):
    """Return list[{"summary_text": str}] always."""
    text = (prompt or '').strip()
    if not text:
        return [{"summary_text": ""}]

    start = timeit.default_timer()
    try:
        out = summarizer(text[:2048], truncation=True)
    except Exception as e:
        logging.error(f"Summarization failed: {e}")
        out = [{"summary_text": text}]
    stop = timeit.default_timer()
    logging.info(f"Summary raw: {out}")
    logging.info(f"Summarize took: {stop - start}")

    # Normalize
    if isinstance(out, list) and out and isinstance(out[0], dict) and 'summary_text' in out[0]:
        return out
    if isinstance(out, str):
        return [{"summary_text": out}]
    return [{"summary_text": text}]


def detect_spam(prompt: str, detector):
    try:
        spam = detector((prompt or '')[:2048], truncation=True)
        if isinstance(spam, list) and spam:
            return spam[0].get('label', 'UNKNOWN')
    except Exception as e:
        logging.error(f"Spam detection failed: {e}")
    return 'UNKNOWN'


def get_tags(prompt: str, tagger):
    """Return list[{"generated_text": str}] always."""
    text = (prompt or '').strip()
    if not text:
        return [{"generated_text": "No tags generated"}]

    try:
        out = tagger(text[:2048], truncation=True)
    except Exception as e:
        logging.error(f"Tagging failed: {e}")
        return [{"generated_text": "No tags generated"}]

    # Normalize a few possible shapes
    if isinstance(out, list) and out:
        first = out[0]
        if isinstance(first, dict) and 'generated_text' in first:
            return [{"generated_text": first['generated_text'] or "No tags generated"}]
        if isinstance(first, str):
            return [{"generated_text": ", ".join(out)}]

    if isinstance(out, str):
        return [{"generated_text": out}]

    return [{"generated_text": "No tags generated"}]