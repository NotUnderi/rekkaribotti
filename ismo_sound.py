import requests
import random
import json
import re


API = "https://ismonator.pikseli.org/ismonator-api/hometta-korviin-ja-viela-pesapallomailalla"
SOUND_LINK = "https://ismonator.pikseli.org/b8b271eb-d549-4d21-a206-0907b15e1246"
headers = requests.utils.default_headers()
headers.update({
#    "Origin": "https://heiniset.fi",
#    "Referer": "https://heiniset.fi/"
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "content-type": "application/json",
    "Origin": "https://ismonator.pikseli.org"
})
def get_sound(msg : str):
    """
    Gets a link to FLAC file of Ismo saying the given message.
    :param message: The message to be spoken by Ismo.
    :return: URL to the FLAC file.
    """
    msg_parsed = replace_numbers(msg)
    seed = random.randint(0, 99999)
    data={"text":f"{msg_parsed}","seed":seed,"outputFormat":"FLAC","character":"ismo"}

    try:
        request = requests.post(f"{API}", headers=headers, data=json.dumps(data))
        if request.status_code == 200:
            raw = request.content
            data = parse_ismonator_response(raw)
            with open(f"{seed}.flac", "wb") as f:
                f.write(data)
            return f"{seed}.flac"
        else:
            raise requests.exceptions.RequestException(f"HTTP: {request.status_code}\n{request.reason}")
    except requests.exceptions.RequestException as e:
        raise

def parse_ismonator_response(raw, boundary=b"--boundary"):
    parts = raw.split(boundary)
    flac_data = None

    for part in parts:
        if b"\r\n\r\n" not in part:
            continue

        headers, body = part.split(b"\r\n\r\n", 1)
        headers = headers.decode(errors="ignore")

        if "audio/flac" in headers:
            flac_data = body

    return flac_data



ONES = [
    "nolla","yksi","kaksi","kolme","neljä","viisi","kuusi","seitsemän","kahdeksan","yhdeksän",
    "kymmenen","yksitoista","kaksitoista","kolmetoista","neljätoista","viisitoista",
    "kuusitoista","seitsemäntoista","kahdeksantoista","yhdeksäntoista"
]

TENS = [
    "", "", "kaksikymmentä","kolmekymmentä","neljäkymmentää","viisikymmentä","kuusikymmentä","seitsemänkymmentä","kahdeksankymmentä","yhdeksänkymmentö"
]



def three_digit_to_words(n: int) -> str:
    """0-999 -> words."""
    if n < 20:
        return ONES[n]

    words = []
    hundreds, rem = divmod(n, 100)

    if hundreds:
        words.append(ONES[hundreds])
        words.append("sataa")

    if rem:
        if rem < 20:
            words.append(ONES[rem])
        else:
            tens, ones = divmod(rem, 10)
            words.append(TENS[tens])
            if ones:
                words.append(ONES[ones])

    return " ".join(words) if words else "zero"


def number_to_words_upto_thousands(num_str: str) -> str:
    """
    Convert an integer string to words.
    Supports 0-999999 (thousands).
    For >= 1_000_000, returns the original string unchanged.
    """

    n = int(num_str)

    thousands, rest = divmod(n, 1000)
    words = []

    if thousands:
        words.append(three_digit_to_words(thousands))
        words.append("tuhatta")

    if rest:
        words.append(three_digit_to_words(rest))
    elif not thousands:
        # exactly 0
        words.append("nolla")

    result = " ".join(words)

    return result


def replace_numbers(text: str) -> str:
    """
    Replace all digit sequences in the text with their word form,
    up to thousands.
    """
    def repl(match: re.Match) -> str:
        digits = match.group(0)
        return number_to_words_upto_thousands(digits)

    return re.sub(r"\d+", repl, text)



if __name__ == "__main__":
    sound_file = get_sound("Tämä on testi.")
    print(f"Sound file saved at: {sound_file}")
