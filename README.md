Baking Lyrics
==============

[www.bakinglyrics.com](www.bakinglyrics.com)

Coverage | Travis | Python Lint
--- | --- | ---
 |  |
 |  |

# Intro

Baking-Lyricis works based on a group of Machine and Deep learning models that generates music lyrics and titles automatically.
Currently available in Spanish and English.

Baking Lyrics was developed by a team of music; machine learning and software development enthusiasts all the way from Buenos Aires, Argentina. Our country is well know for its rock scene so we were tempted on using a 100% rock corpus but our metal loving friends convinced us of accepting other genres. Oh and there is some cumbia and reggaeton in there as well!

## Baking Lyrics: An automatic lyrics generator

Be a rock star using machine learning to generate lyrics!
Baking lyrics is an automatic generator of lyrics based on a natural language model that is trained using the largest database of lyrics online.
The vast corpus contains all the lyrics of the most popular bands and singers of our time. This corpus was used to train a language model that reproduces the style of each band or singer. If you ever wanted to reproduce the talent of your favorite songwriter, now is the time!

# How-to

- Clone the repo.
- Create a python venv in your SO
- Source it: `source bar/foo/venv/your-venv/bin/activate`
- Run `pip install -r requirements/dev.txt`
- Create the instance folder in the `api` dir and add a file named: config.py under it.
- Add the following content to to it:
```python
SECRET_KEY = 'Sm9obiBTY2hyb20ga2lja3MgYXNz'
STRIPE_API_KEY = 'SmFjb2IgS2FwbGFuLU1vc3MgaXMgYSBoZXJv'
```
- Request the current models to [Andrei Rukavina](mailto:rukavina.andrei@gmailcom)
- Put the file under: `/api/resources/`
- Add the following ENV variable into your favourite OS: `APP_CONFIG_FILE=/Users/<your name>/GitHub/Baking-Lyrics/config/development.py`
- Run /run.py

# Models

While using the app you will be able to choose from:

## Deep-Learning models

Text summarization is a problem in natural language processing of creating a short, accurate, and fluent summary of a source document.

The Encoder-Decoder recurrent neural network architecture developed for machine translation has proven effective when applied to the problem of text summarization.

It can be difficult to apply this architecture in the Keras deep learning library, given some of the flexibility sacrificed to make the library clean, simple, and easy to use.

## Encoder-Decoder Architecture

*Based on: [machinelearningmastery.com](https://machinelearningmastery.com/encoder-decoder-models-text-summarization-keras/)*

The Encoder-Decoder architecture is a way of organizing recurrent neural networks for sequence prediction problems that have a variable number of inputs, outputs, or both inputs and outputs.

The architecture involves two components: an encoder and a decoder.

* Encoder: The encoder reads the entire input sequence and encodes it into an internal representation, often a fixed-length vector called the context vector.
* Decoder: The decoder reads the encoded input sequence from the encoder and generates the output sequence.

For more about the Encoder-Decoder architecture, see the post:

* Encoder-Decoder Long Short-Term Memory Networks

Both the encoder and the decoder submodels are trained jointly, meaning at the same time.

This is quite a feat as traditionally, challenging natural language problems required the development of separate models that were later strung into a pipeline, allowing error to accumulate during the sequence generation process.

The entire encoded input is used as context for generating each step in the output. Although this works, the fixed-length encoding of the input limits the length of output sequences that can be generated.

An extension of the Encoder-Decoder architecture is to provide a more expressive form of the encoded input sequence and allow the decoder to learn where to pay attention to the encoded input when generating each step of the output sequence.

This extension of the architecture is called attention.
The Encoder-Decoder architecture with attention is popular for a suite of natural language processing problems that generate variable length output sequences, such as text summarization.
The application of architecture to text summarization is as follows:

* Encoder: The encoder is responsible for reading the source document and encoding it to an internal representation.
* Decoder: The decoder is a language model responsible for generating each word in the output summary using the encoded representation of the source document.

## N-Gram models

N-gram models are probabilistic models that assign probabilities on the “next” word in a sequence, given the n-1 previous words. This algorithm takes in an array of Strings (the songs in our corpus), and uses punctuation to select beginning and end tokens on each sentence.
Baking lyrics uses a trigram model, since it calculates the frecuencies in which every three-word combination appear on each band's corpus, and extrapolates the probabilities from there.
