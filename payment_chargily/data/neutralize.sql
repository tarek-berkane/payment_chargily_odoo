-- disable chargily payment provider
UPDATE payment_provider
   SET chargily_public_token = NULL,
      chargily_secret_token = NULL;
