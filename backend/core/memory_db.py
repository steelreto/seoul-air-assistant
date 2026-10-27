"""Firebase 키 없이 로컬에서 테스트하기 위한 아주 작은 가짜 Firestore.

이 프로젝트가 실제로 쓰는 Firestore 기능만 흉내 낸다:
  db.collection(name).document(id).get() / set() / update() / delete()
  db.collection(name).document()          -> 자동 ID
  db.collection(name).stream()
  db.batch()                              -> seed 스크립트용
운영(Render)에서는 사용하지 않는다.
"""
import copy
import threading
import uuid


class _Snapshot:
    def __init__(self, doc_id: str, data: dict | None):
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict | None:
        return copy.deepcopy(self._data) if self._data is not None else None


class _DocRef:
    def __init__(self, store: dict, lock: threading.Lock, doc_id: str):
        self._store = store
        self._lock = lock
        self.id = doc_id

    def get(self) -> _Snapshot:
        with self._lock:
            return _Snapshot(self.id, copy.deepcopy(self._store.get(self.id)))

    def set(self, data: dict) -> None:
        with self._lock:
            self._store[self.id] = copy.deepcopy(data)

    def update(self, data: dict) -> None:
        with self._lock:
            if self.id not in self._store:
                raise KeyError(f"No document to update: {self.id}")
            self._store[self.id].update(copy.deepcopy(data))

    def delete(self) -> None:
        with self._lock:
            self._store.pop(self.id, None)


class _Collection:
    def __init__(self, store: dict, lock: threading.Lock):
        self._store = store
        self._lock = lock

    def document(self, doc_id: str | None = None) -> _DocRef:
        return _DocRef(self._store, self._lock, doc_id or uuid.uuid4().hex[:20])

    def stream(self):
        with self._lock:
            items = [(k, copy.deepcopy(v)) for k, v in self._store.items()]
        for k, v in items:
            yield _Snapshot(k, v)


class _Batch:
    def __init__(self):
        self._ops = []

    def set(self, ref: _DocRef, data: dict) -> None:
        self._ops.append((ref, data))

    def commit(self) -> None:
        for ref, data in self._ops:
            ref.set(data)
        self._ops.clear()


class MemoryClient:
    def __init__(self):
        self._collections: dict[str, dict] = {}
        self._lock = threading.Lock()

    def collection(self, name: str) -> _Collection:
        return _Collection(self._collections.setdefault(name, {}), self._lock)

    def batch(self) -> _Batch:
        return _Batch()
