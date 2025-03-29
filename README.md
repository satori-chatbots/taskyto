1# Language and library for chatbot development

## Usage

To run a specific chatbot there is a script (`main.py`) which is in charge of loading the chatbot and interpret the contents of the yaml files. The yaml files must be located in some folder. For example, `examples/yaml/bike-shop`. Then:

```
python -m taskyto.main --chatbot examples/yaml/bike-shop/
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
