# Language and library for chatbot development

## Usage

To run a specific chatbot there is a script (`main.py`) which is in charge of loading the chatbot and interpret the contents of the yaml files. The yaml files must be located in some folder. For example, `examples/yaml/bike-shop`. Then:

```
python src/main.py --chatbot examples/yaml/bike-shop/
```

## Configuration

API keys can be set as environment variables or in a `keys.properties` files.
The most important API key is `OPENAI_API_KEY`.

The `keys.properties` has the following form:

```
[keys]
SERPAPI_API_KEY=anapiforgooglesearch
OPENAI_API_KEY=theopenaikey
```

## Other examples

There are some initial examples developed directly using the API. They are mostly incomplete and likely not working.

### Bike shop

Requires `OPENAI_API_KEY`.

```
PYTHONPATH=src/ python3 examples/manual/bike-shop/bike_shop.py 
```

In Windows, use `set PYTHONPATH=src` before executing the command.

### Healthy AI

A chatbot to answer questions about healthy habits. 

To make this example work you need to manually add a book in PDF with the name `data/body-building.pdf` so that the system can index it to answer queries about this topic.

Requires `SERPAPI_API_KEY` and `OPENAI_API_KEY`.

```
PYTHONPATH=src/ python3 examples/manual/healthy-ai/healthy_ai.py 
```

