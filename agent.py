"""
agent.py

Núcleo do agente inteligente do Challenge Alura Agente.

O agente implementa uma abordagem de RAG (Retrieval-Augmented Generation):
1. Carrega o documento de conhecimento (CSV com perguntas e respostas de FAQ).
2. Gera embeddings de cada trecho do documento usando o modelo de embeddings do Gemini.
3. Quando o usuário faz uma pergunta, gera o embedding da pergunta e busca os trechos
   mais relevantes por similaridade de cosseno.
4. Envia os trechos recuperados + a pergunta para o modelo generativo do Gemini,
   que responde com base apenas no conteúdo do documento.
"""

import os
import numpy as np
import pandas as pd
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
GENERATIVE_MODEL = os.getenv("GENERATIVE_MODEL", "gemini-2.0-flash")
DATA_PATH = os.getenv("DATA_PATH", os.path.join(os.path.dirname(__file__), "data", "faq_techstore.csv"))

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Variável de ambiente GEMINI_API_KEY não definida. "
        "Crie um arquivo .env baseado no .env.example ou exporte a variável no ambiente."
    )

genai.configure(api_key=GEMINI_API_KEY)


class DocumentAgent:
    """Agente que responde perguntas com base em um documento CSV (FAQ)."""

    def __init__(self, csv_path: str = DATA_PATH):
        self.csv_path = csv_path
        self.chunks = []          # lista de textos (pergunta + resposta) usados como contexto
        self.embeddings = None    # matriz numpy com os embeddings de cada chunk
        self._load_and_index()

    def _load_and_index(self):
        """Lê o CSV e cria os embeddings de cada linha (chunk) do documento."""
        df = pd.read_csv(self.csv_path)

        # Cada linha do FAQ vira um "chunk" de contexto no formato pergunta/resposta.
        self.chunks = [
            f"Pergunta: {row['pergunta']}\nResposta: {row['resposta']}"
            for _, row in df.iterrows()
        ]

        embeddings = []
        for chunk in self.chunks:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=chunk,
                task_type="retrieval_document",
            )
            embeddings.append(result["embedding"])

        self.embeddings = np.array(embeddings)

    def _embed_query(self, query: str) -> np.ndarray:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query,
            task_type="retrieval_query",
        )
        return np.array(result["embedding"])

    def _retrieve(self, query: str, top_k: int = 3):
        """Retorna os `top_k` chunks mais relevantes para a pergunta do usuário."""
        query_embedding = self._embed_query(query)

        # Similaridade de cosseno entre a pergunta e todos os chunks do documento
        norms = np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        norms[norms == 0] = 1e-10
        similarities = np.dot(self.embeddings, query_embedding) / norms

        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [self.chunks[i] for i in top_indices]

    def ask(self, question: str) -> str:
        """Responde a uma pergunta do usuário com base no documento carregado."""
        relevant_chunks = self._retrieve(question)
        context = "\n\n".join(relevant_chunks)

        prompt = f"""Você é um assistente de atendimento ao cliente da TechStore.
Responda à pergunta do usuário utilizando SOMENTE as informações do contexto abaixo,
retirado da base de conhecimento (FAQ) da empresa.

Se a resposta não estiver no contexto, diga educadamente que não possui essa
informação na base de conhecimento e sugira contato com o suporte.

Contexto:
{context}

Pergunta do usuário: {question}

Resposta:"""

        model = genai.GenerativeModel(GENERATIVE_MODEL)
        response = model.generate_content(prompt)
        return response.text.strip()


# Instância única (singleton) usada pela aplicação Flask
_agent_instance = None


def get_agent() -> DocumentAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DocumentAgent()
    return _agent_instance
