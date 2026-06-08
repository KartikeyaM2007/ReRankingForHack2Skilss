from __future__ import annotations
from datetime import date
import re

TODAY = date(2026, 6, 8)

TARGET_LOCATIONS_STRONG = {"pune", "noida"}
TARGET_LOCATIONS_GOOD = {"delhi", "gurgaon", "gurugram", "mumbai", "hyderabad", "bangalore", "bengaluru"}
INDIA_CITY_SIGNALS = {
    "pune", "noida", "delhi", "gurgaon", "gurugram", "hyderabad", "mumbai", "bangalore", "bengaluru",
    "chennai", "kolkata", "coimbatore", "kochi", "trivandrum", "jaipur", "indore", "ahmedabad",
    "chandigarh", "bhubaneswar", "vizag"
}

SERVICE_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "hcl", "tech mahindra",
    "mindtree", "mphasis", "genpact"
}
SERVICE_INDUSTRIES = {"it services", "consulting"}
PRODUCT_INDUSTRIES = {
    "software", "saas", "e-commerce", "fintech", "food delivery", "edtech", "adtech", "transportation",
    "insurance tech", "gaming", "healthtech", "healthtech ai", "conversational ai", "ai/ml", "ai services",
    "voice ai", "internet", "media", "consumer electronics"
}
PRODUCT_COMPANIES = {
    "swiggy", "zomato", "flipkart", "meesho", "razorpay", "cred", "phonepe", "paytm", "freshworks",
    "zoho", "inmobi", "ola", "dream11", "nykaa", "pharmeasy", "upgrad", "unacademy", "vedantu",
    "policybazaar", "sarvam ai", "krutrim", "yellow.ai", "haptik", "observe.ai", "saarthi.ai",
    "verloop.io", "rephrase.ai", "niramai", "wysa", "aganitha", "glance", "mad street den",
    "google", "meta", "amazon", "microsoft", "apple", "netflix", "salesforce", "linkedin", "adobe", "uber"
}
TOP_TECH_COMPANIES = {"google", "meta", "amazon", "microsoft", "apple", "netflix", "salesforce", "linkedin", "adobe", "uber"}

TITLE_WEIGHTS = {
    "senior ai engineer": 1.00,
    "lead ai engineer": 0.995,
    "senior machine learning engineer": 0.985,
    "staff machine learning engineer": 0.975,
    "search engineer": 0.965,
    "recommendation systems engineer": 0.965,
    "applied ml engineer": 0.955,
    "senior applied scientist": 0.93,
    "machine learning engineer": 0.91,
    "ai engineer": 0.90,
    "senior nlp engineer": 0.90,
    "nlp engineer": 0.84,
    "senior data scientist": 0.80,
    "senior software engineer (ml)": 0.78,
    "ml engineer": 0.75,
    "data scientist": 0.68,
    "ai research engineer": 0.54,
    "ai specialist": 0.48,
    "junior ml engineer": 0.23,
    "computer vision engineer": 0.20,
    "senior software engineer": 0.20,
    "data engineer": 0.16,
    "analytics engineer": 0.14,
    "backend engineer": 0.14,
    "cloud engineer": 0.08,
    "devops engineer": 0.08,
    "software engineer": 0.08,
    "full stack developer": 0.05,
    "frontend engineer": 0.02,
}
NON_TECH_TITLES = {
    "business analyst", "hr manager", "mechanical engineer", "accountant", "project manager", "customer support",
    "operations manager", "content writer", "sales executive", "civil engineer", "graphic designer", "marketing manager"
}

# Skill weights represent JD-specific evidence, not generic ML prestige.
CORE_SKILLS = {
    "python": 6.0,
    "information retrieval": 10.0,
    "information retrieval systems": 10.5,
    "search infrastructure": 10.5,
    "search backend": 9.5,
    "search & discovery": 9.5,
    "ranking systems": 10.0,
    "learning to rank": 9.0,
    "recommendation systems": 8.0,
    "semantic search": 8.5,
    "vector search": 8.0,
    "embeddings": 8.0,
    "sentence transformers": 7.0,
    "vector representations": 7.5,
    "text encoders": 7.0,
    "content matching": 7.0,
    "indexing algorithms": 7.0,
    "bm25": 6.8,
    "faiss": 6.2,
    "pinecone": 5.8,
    "qdrant": 5.6,
    "milvus": 5.6,
    "weaviate": 5.6,
    "opensearch": 5.5,
    "elasticsearch": 5.3,
    "pgvector": 5.0,
    "nlp": 5.5,
    "natural language processing": 5.5,
    "machine learning": 4.6,
    "deep learning": 3.7,
    "llms": 4.4,
    "rag": 4.8,
    "fine-tuning llms": 4.6,
    "lora": 3.4,
    "qlora": 3.6,
    "peft": 3.4,
    "hugging face transformers": 4.2,
    "pytorch": 4.0,
    "tensorflow": 2.7,
    "scikit-learn": 3.6,
    "mlflow": 3.0,
    "kubeflow": 2.8,
    "bentoml": 2.6,
    "weights & biases": 2.4,
    "fastapi": 1.8,
    "feature engineering": 2.9,
    "model adaptation": 3.5,
    "open-source ml libraries": 3.0,
    "document processing": 2.5,
}
VECTOR_DB_SKILLS = {"faiss", "pinecone", "qdrant", "milvus", "weaviate", "opensearch", "elasticsearch", "pgvector"}
RETRIEVAL_SKILLS = {"information retrieval", "information retrieval systems", "semantic search", "vector search", "embeddings", "sentence transformers", "bm25", "vector representations", "text encoders", "content matching", "indexing algorithms"}
RANKING_SKILLS = {"ranking systems", "learning to rank", "recommendation systems"}
FRAMEWORK_ONLY_SKILLS = {"langchain", "llamaindex", "prompt engineering"}
NEGATIVE_DOMAIN_SKILLS = {
    "computer vision", "object detection", "image classification", "opencv", "yolo", "cnn", "gans", "diffusion models",
    "speech recognition", "tts", "asr", "robotics", "reinforcement learning", "time series", "forecasting"
}

# Regex groups. Each group returns a capped normalized evidence score.
EVIDENCE_PATTERNS = {
    "production": [
        (r"\bproduction\b|\bshipped\b|\bdeployed\b|\bserved\b|\boperated\b|\bbuilt and shipped\b", 1.0),
        (r"real users|live users|user[- ]facing|customer[- ]facing|productionized|rollout|launched", 1.2),
        (r"p95|latency|throughput|index refresh|embedding drift|retrieval[- ]quality regression|incremental refresh", 1.4),
    ],
    "retrieval": [
        (r"hybrid retrieval|dense retrieval|sparse retrieval|embedding[- ]based retrieval|semantic search|vector search", 1.8),
        (r"bm25|faiss|hnsw|pinecone|qdrant|milvus|weaviate|opensearch|elasticsearch|pgvector", 1.2),
        (r"sentence[- ]transformers?|bge|e5|openai embeddings|text embedding|nearest[- ]neighbor", 1.1),
    ],
    "ranking_eval": [
        (r"learning[- ]to[- ]rank|ranking layer|relevance model|re[- ]ranker|ranker|relevance labeling", 1.7),
        (r"ndcg|mrr|map\b|recall@|precision@|offline evaluation|offline[- ]online|a/b test|ab test|online experiment", 1.7),
        (r"recruiter feedback|human judgments|click[- ]through|engagement metrics|conversion metric", 1.2),
    ],
    "recsys_marketplace": [
        (r"recommendation system|discovery feed|search product|search and discovery|marketplace|matching engine", 1.4),
        (r"candidate[- ]jd matching|candidate matching|candidate profiles|recruiter[- ]facing|recruiter workflows|talent intelligence", 2.0),
        (r"personalization|collaborative filtering|matrix factorization|cold start|feed ranking", 1.0),
    ],
    "scale": [
        (r"\d+\s*(m|million)\+?\s+(queries|users|documents|profiles|items)|\d+\s*gb|\d+\s*k\+?\s+(documents|queries)", 1.2),
        (r"large[- ]scale|at scale|serving \d+|corpus of \d+", 1.0),
    ],
    "llm_depth": [
        (r"fine[- ]tuned|lora|qlora|peft|preference pairs|eval harness|llm[- ]based re[- ]ranker", 1.0),
        (r"rag[- ]based ranking|rag pipeline|llama|mistral|transformers", 0.7),
    ],
    "shipper": [
        (r"working v1|ship.*week|scrappy|founding|0 to 1|zero to one|own.*end[- ]to[- ]end|mentor", 0.9),
        (r"wrote production code|hands[- ]on|code quality|debugging production", 1.1),
    ],
}
NEGATIVE_PATTERNS = {
    "research_only": [(r"pure research|academic lab|research[- ]only|publication[- ]focused|no production", 2.5)],
    "framework_only": [(r"langchain tutorial|prompt engineering only|wrapper around openai|toy project|prototype only|demo only", 2.0)],
    "wrong_domain": [(r"computer vision|object detection|image classification|speech recognition|robotics|asr|tts", 0.55)],
    "services_only_text": [(r"consulting delivery|client projects|staff augmentation|support ticket|maintenance project", 0.8)],
}

COMPILED_EVIDENCE = {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in EVIDENCE_PATTERNS.items()}
COMPILED_NEGATIVE = {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in NEGATIVE_PATTERNS.items()}

JD_FACETS = {
    "production_retrieval": {
        "terms": ["production", "shipped", "semantic search", "vector search", "embedding", "retrieval", "faiss", "pinecone", "qdrant", "hybrid retrieval", "index refresh"],
        "weight": 0.24,
    },
    "ranking_evaluation": {
        "terms": ["ranking", "learning to rank", "relevance", "ndcg", "mrr", "map", "a/b", "offline evaluation", "human judgments", "click-through"],
        "weight": 0.22,
    },
    "product_ml": {
        "terms": ["product", "marketplace", "recommendation", "discovery", "search product", "user-facing", "engagement", "launched"],
        "weight": 0.18,
    },
    "hrtech_matching": {
        "terms": ["candidate", "recruiter", "jd matching", "talent", "profile", "sourcing", "candidate-jd"],
        "weight": 0.14,
    },
    "senior_shipper": {
        "terms": ["senior", "lead", "owned", "end-to-end", "production code", "mentor", "scrappy", "v1", "debugging"],
        "weight": 0.12,
    },
    "llm_systems": {
        "terms": ["llm", "rag", "fine-tuned", "lora", "qlora", "peft", "reranker", "transformers"],
        "weight": 0.10,
    },
}
