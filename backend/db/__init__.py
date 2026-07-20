from config import DB_PATH
from db.connection import get_conn
from db.schema import init_db
from db.documents_repo import (
    upsert_document, get_document, update_document, search_documents, count_documents,
    bulk_update_documents, delete_document, get_expiring_documents, get_tax_documents,
    find_similar_by_features, get_document_by_hash, get_document_by_path,
    get_similar_by_simhash, get_all_file_paths
)
from db.protected_hashes_repo import (
    protect_document_hash, unprotect_document_hash, get_protected_hash,
    is_hash_protected, list_protected_hashes,
)
from db.stats_repo import get_stats

from db.embeddings_repo import (
    insert_embedding, get_embedding, get_all_embeddings, delete_embedding,
    find_similar_documents
)

from db.traces_repo import (
    insert_trace, get_traces_for_document, delete_traces_for_document
)
