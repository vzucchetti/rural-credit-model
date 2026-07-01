# %%
import httpx
from io import BytesIO
from src.utils.logging import get_logger


log = get_logger("ingestion")


def fetch_to_buffer(
    url: str, timeout: int = 300, chunk_size: int = 8192
) -> BytesIO | None:
    """ """
    buf = BytesIO()

    try:
        log.info("Iniciando requisição HTTP para a URL: %s", url)
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
            if r.status_code == 404:
                log.warning("Arquivo não encontrado (404): %s", url)
                return None
            r.raise_for_status()
            for chunk in r.iter_bytes(chunk_size=chunk_size):
                buf.write(chunk)
        size_mb = buf.getbuffer().nbytes / 1e6
        log.info("Download concluído com sucesso em %s! Tamanho: %.2f MB", url, size_mb)
        buf.seek(0)
        return buf
    except httpx.HTTPStatusError as e:
        log.error("Erro HTTP ao tentar acessar %s: %s", url, e)
        buf.close()
        raise
    except httpx.RequestError as e:
        log.error(
            "Erro de rede ou timeout após %s segundos ao conectar em %s: %s",
            timeout,
            url,
            e,
        )
        buf.close()
        raise
    except Exception as e:
        log.error("Erro inesperado ao baixar %s: %s", url, e)
        buf.close()
        raise
