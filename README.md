# Experiments with Chatbots and LLMs

## Examples

### Bike shop

Requires `OPENAI_API_KEY`.

```
python bike_shop.py
```

### Healthy AI

A chatbot to answer questions about healthy habits. 

To make this example work you need to manually add a book in PDF with the name `data/body-building.pdf` so that the system can index it to answer queries about this topic.

Requires `SERPAPI_API_KEY` and `OPENAI_API_KEY`.

```
python healthy_ai.py
```

## Configuration

API keys can be set as environment variables or in a `keys.properties` files.
