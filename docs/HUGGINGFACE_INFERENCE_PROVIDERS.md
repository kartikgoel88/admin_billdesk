# Hugging Face Inference Providers (Option A)

If you get **"the request model is not supported by any provider you have enabled"** when using `llm.provider: huggingface` with a model like `meta-llama/Llama-3.1-70B-Instruct`, you need to enable a provider that serves that model.

## Step 1: See which providers support your model

1. Open the model on the Hub, e.g. [meta-llama/Llama-3.1-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct).
2. Check the **Inference** widget on the right (or the model’s “Inference” / “Providers” section).
3. For **Llama-3.1-70B-Instruct**, the available providers are typically **Fireworks AI** and **Scaleway**.

## Step 2: Enable Inference Providers in your account

1. Go to **Hugging Face → Settings → Inference Providers**:  
   **https://huggingface.co/settings/inference-providers**
2. Log in if needed.
3. Find **Fireworks AI** and **Scaleway** (or the providers listed for your model).
4. **Enable** them (turn them on / add them to your preferred list).
5. Optionally set **provider order** so your preferred one is used first (e.g. cheapest or fastest).
6. (Optional) If you have your own API key for a provider (e.g. Fireworks), you can add it in that settings page so requests use your key and quota.

## Step 3: Use a token with Inference Provider permission

1. Go to **Settings → Access Tokens**: **https://huggingface.co/settings/tokens**
2. Create a **Fine-grained** token (or edit an existing one).
3. Enable the **“Make calls to Inference Providers”** permission.
4. Use this token in your app as `HUGGINGFACEHUB_API_TOKEN` (in `.env` or `config.yaml`).

## Step 4: Retry the app

Set in `src/config/config.yaml`:

```yaml
llm:
  provider: huggingface
  providers:
    huggingface:
      model: meta-llama/Llama-3.1-70B-Instruct
      api_key_env: HUGGINGFACEHUB_API_TOKEN
      max_new_tokens: 2048
```

Ensure `HUGGINGFACEHUB_API_TOKEN` is set in your environment or `.env`. Then run the app again; requests will go through the provider(s) you enabled.

## Quick links

| What | URL |
|------|-----|
| Inference Provider settings | https://huggingface.co/settings/inference-providers |
| Access tokens | https://huggingface.co/settings/tokens |
| Models with providers | https://huggingface.co/inference/models |
| Llama-3.1-70B-Instruct | https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct |
