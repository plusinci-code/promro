# app/modules/llm.py
import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI, BadRequestError

load_dotenv()

def get_client(api_key: Optional[str] = None) -> OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing. Provide in sidebar or .env")
    return OpenAI(api_key=key)

def complete(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system: Optional[str] = None,
) -> str:
    """
    Dayanıklı chat completion:
    - Önce modern parametre (max_completion_tokens) + temperature ile dener.
    - Model temperature'ı sadece 1 destekliyorsa, temperature'sız tekrar dener.
    - Model max_completion_tokens desteklemiyorsa, legacy max_tokens ile tekrar dener.
    """
    client = get_client(api_key)
    _model = model or os.getenv("OPENAI_MODEL", "gpt-4")
    _temp = float(temperature if temperature is not None else os.getenv("OPENAI_TEMPERATURE", 0.7))
    _max  = int(max_tokens  if max_tokens  is not None else os.getenv("OPENAI_MAX_TOKENS", 2000))

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    def call(use_new_tokens: bool = True, include_temp: bool = True):
        kwargs = dict(model=_model, messages=messages)
        if use_new_tokens:
            kwargs["max_completion_tokens"] = _max
        else:
            kwargs["max_tokens"] = _max
        if include_temp:
            kwargs["temperature"] = _temp
        return client.chat.completions.create(**kwargs)

    # En basit yaklaşım - sadece gerekli parametreler
    try:
        response = client.chat.completions.create(
            model=_model,
            messages=messages,
            temperature=_temp
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("OpenAI API returned None content")
        return content.strip()
    except Exception as e:
        # Son çare: temperature olmadan
        try:
            response = client.chat.completions.create(
                model=_model,
                messages=messages
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI API returned None content")
            return content.strip()
        except Exception:
            raise e

def translate(
    text: str,
    target_lang: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    Basit çeviri yardımcı fonksiyonu. Model temperature'ı desteklemiyorsa,
    complete() otomatik olarak temperaturesız fallback yapar.
    """
    prompt = (
        f"Translate the following text into {target_lang} with native-level fluency. "
        f"Preserve meaning and tone. Return only the translation.\n\n{text}"
    )
    return complete(
        prompt,
        api_key=api_key,
        model=model,
        temperature=0.2,
        max_tokens=800
    )
