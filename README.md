# Language and library for chatbot development

## Installation

Install using pip with:

```
pip install taskyto
```

## Usage

To load a chatbot and interact with it using the console use:

```
taskyto --chatbot <your-chatbot-folder>
```

To load a chatbot and expose it using a webserver:

```
taskyto-serve --chatbot <your-chatbot-folder>
```


## Usage (Developer)

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
