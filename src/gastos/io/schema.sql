-- Modelo canônico (CLAUDE.md §5) — parte 1: purchase/purchase_item + suporte a OAuth.
--
-- bank_transaction e reconciliation ficam de fora deste arquivo de propósito:
-- projetar a tabela de reconciliation exige entender as regras de matching
-- (CLAUDE.md §6, Etapa 5) primeiro, sob risco de migrar um schema errado.
-- Ver docs/decisions/0002-agregado-purchase-e-token-oauth.md.

CREATE TABLE IF NOT EXISTS purchase (
    purchase_id  TEXT PRIMARY KEY,
    source       TEXT NOT NULL CHECK (source IN ('mercadolivre', 'nfce')),
    purchased_at TIMESTAMPTZ NOT NULL,
    merchant     TEXT NOT NULL,
    gross_amount NUMERIC(14, 2) NOT NULL,
    raw          JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS purchase_item (
    purchase_id  TEXT NOT NULL REFERENCES purchase (purchase_id),
    line_no      INTEGER NOT NULL,
    description  TEXT NOT NULL,
    quantity     NUMERIC(14, 4) NOT NULL,
    unit_amount  NUMERIC(14, 4) NOT NULL,
    line_amount  NUMERIC(14, 2) NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('product', 'shipping', 'discount', 'service_fee')),
    PRIMARY KEY (purchase_id, line_no)
);

-- Persistência do refresh_token do Mercado Livre (CLAUDE.md §4.1: "o refresh
-- precisa ser persistido e rotacionado"). Uma linha por provedor de OAuth.
CREATE TABLE IF NOT EXISTS oauth_token (
    provider      TEXT PRIMARY KEY,
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
