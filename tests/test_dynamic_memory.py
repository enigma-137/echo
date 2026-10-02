import asyncio
import unittest

from app.database import SessionLocal, init_db
from app.memory.manager import MemoryManager, cosine_similarity
from app.models.memory import MemoryKind
from app.services.profile import ProfileService


class TestDynamicMemory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()

    async def test_cosine_similarity(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0)
        self.assertAlmostEqual(cosine_similarity(v1, v3), 0.0)

    async def test_profile_service(self):
        async with SessionLocal() as db:
            mgr = MemoryManager(db)
            user = await mgr.get_or_create_default_user()
            service = ProfileService(db)

            profile = await service.get_or_create_profile(user)
            self.assertIn("name", profile)
            self.assertIn("lifestyle", profile)

            # Test updating profile
            updated = await service.update_profile(user.id, {"crush": {"name": "Ileri", "status": "crush"}})
            self.assertEqual(updated.get("crush", {}).get("name"), "Ileri")

    async def test_memory_storage_and_search(self):
        async with SessionLocal() as db:
            mgr = MemoryManager(db)
            user = await mgr.get_or_create_default_user()

            # Store memory with unique embedding vector
            unique_vector = [0.9] + [0.01] * 383
            mem = await mgr.store_memory(
                user_id=user.id,
                content="Emmanuel has a crush on Ileri and hopes to go on a date with her.",
                kind=MemoryKind.LONG_TERM,
                tags="crush,ileri,test",
                embedding=unique_vector,
            )
            self.assertIsNotNone(mem.id)

            # Semantic search
            results = await mgr.search_semantic_memories(user.id, unique_vector, limit=5)
            self.assertTrue(len(results) > 0)
            result_ids = [m.id for m, score in results]
            self.assertIn(mem.id, result_ids)


if __name__ == "__main__":
    unittest.main()
