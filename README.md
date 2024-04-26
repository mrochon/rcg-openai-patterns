# OpenAI Toolkit: Patterns and Practices for RAG / Bring Your Own Data

Here, you'll find a collection of straightforward examples showcasing different ways to integrate and utilize OpenAI's capabilities. We've broken down each method into clear, manageable parts, making it easy for anyone to grasp and apply, regardless of their technical background. Our aim is to demystify AI, one pattern at a time, using plain language and practical examples. Whether you're a beginner or looking to expand your toolkit, this resource is designed for you!

## OpenAI Review

When delving into the world of OpenAI, there are two fundamental concepts that are essential to understand:

- Embeddings: The process of converting data, such as text or images, into a vector format. 

- Chat Completion / General LLM: This refers to the use of large language models (LLM) like GPT (Generative Pre-trained Transformer) for generating text.

### Embeddings

Embeddings are a powerful technique used to convert raw data—like text, images, or even sounds—into a structured, numerical format known as vectors. These vectors are constructed in such a way that they capture the essential aspects of the data, like meaning, context, or relationships, in a format that machines can understand and process.

![alt text](diagrams/embeddingsGeneral.png)

#### Embeddings Model Specifications

| Model ID                             | Max Request (tokens) | Output Dimensions 
| ------------------------------------ | -------------------- | ----------------- |
| `text-embedding-ada-002 (version 2)` | 8,191                | 1,536             |
| `text-embedding-ada-002 (version 1)` | 2,046                | 1,536             |
| `text-embedding-3-large`             | 8,191                | 3,072             |
| `text-embedding-3-small`             | 8,191                | 1,536             |

#### Understanding the Specifications

- **Model ID**: Identifies the specific version of the embedding model
  - The model you will specify when calling the embeddings endpoint
- **Max Request (tokens)**: Indicates the maximum number of tokens that can be processed in a single request 
  - This comes into play when we have lots of data that will need to be embedded.
  - When planning to embed a large ammount of data we will need to break it up into 'chunks' <= to the Max Request tokens of the respective embedding model  
- **Output Dimensions**: Specifies the size of the output vector for each embedding.
  - After embedding we will need a place to store the vector. A few data store options include Azure AI Search, MongoDB, Redis Enterprise 
  - When configuring the data store we need to ensure that the vector field dimensions are set to the output dimensions of our model





