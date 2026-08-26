FROM apache/airflow:2.9.3-python3.12

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY --chown=airflow:root pyproject.toml uv.lock /opt/airflow/
COPY --chown=airflow:root src /opt/airflow/src

# Instala o pacote gastos (src/gastos) e suas dependências de runtime no
# Python da imagem oficial do Airflow, usando uv para ficar consistente com
# o fluxo de desenvolvimento local (ver CLAUDE.md §3). O pacote local
# precisa estar copiado antes deste passo pois requirements.txt inclui
# "-e ." (instalação editável a partir do source já presente na imagem).
RUN pip install --no-cache-dir "uv>=0.5" \
    && cd /opt/airflow \
    && uv export --frozen --no-dev --no-hashes -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt
