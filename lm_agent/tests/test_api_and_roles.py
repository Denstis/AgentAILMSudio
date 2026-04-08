"""
Тесты для API клиента и движка ролей.
"""
import pytest
from pathlib import Path
import json
import tempfile


class TestModelCapabilities:
    """Тесты для ModelCapabilities."""
    
    def test_default_capabilities(self):
        from lm_agent.api.models import ModelCapabilities
        
        caps = ModelCapabilities()
        assert caps.vision is False
        assert caps.tool_use is False
        assert caps.reasoning is False
    
    def test_capabilities_to_dict(self):
        from lm_agent.api.models import ModelCapabilities
        
        caps = ModelCapabilities(vision=True, tool_use=True)
        d = caps.to_dict()
        
        assert d['vision'] is True
        assert d['tool_use'] is True
        assert d['reasoning'] is False
    
    def test_capabilities_from_dict(self):
        from lm_agent.api.models import ModelCapabilities
        
        data = {'vision': True, 'json_mode': True}
        caps = ModelCapabilities.from_dict(data)
        
        assert caps.vision is True
        assert caps.json_mode is True


class TestModelInfo:
    """Тесты для ModelInfo."""
    
    def test_model_info_creation(self):
        from lm_agent.api.models import ModelInfo, ModelCapabilities
        
        caps = ModelCapabilities(tool_use=True)
        model = ModelInfo(
            id='test-model',
            name='Test Model',
            context_window=8192,
            capabilities=caps
        )
        
        assert model.id == 'test-model'
        assert model.context_window == 8192
        assert model.capabilities.tool_use is True
    
    def test_model_info_str(self):
        from lm_agent.api.models import ModelInfo
        
        model = ModelInfo(id='my-model', name='My Model')
        assert str(model) == 'My Model (my-model)'
    
    def test_model_info_to_dict(self):
        from lm_agent.api.models import ModelInfo
        
        model = ModelInfo(id='test', name='Test')
        d = model.to_dict()
        
        assert d['id'] == 'test'
        assert d['name'] == 'Test'
        assert isinstance(d['capabilities'], dict)


class TestModelList:
    """Тесты для ModelList."""
    
    def test_model_list_add(self):
        from lm_agent.api.models import ModelList, ModelInfo
        
        ml = ModelList()
        model = ModelInfo(id='m1', name='Model 1')
        ml.add(model)
        
        assert len(ml) == 1
        assert ml[0].id == 'm1'
    
    def test_model_list_get_by_id(self):
        from lm_agent.api.models import ModelList, ModelInfo
        
        ml = ModelList()
        ml.add(ModelInfo(id='model-1', name='First'))
        ml.add(ModelInfo(id='model-2', name='Second'))
        
        found = ml.get_by_id('model-2')
        assert found is not None
        assert found.name == 'Second'
        
        not_found = ml.get_by_id('nonexistent')
        assert not_found is None
    
    def test_model_list_filter_by_capability(self):
        from lm_agent.api.models import ModelList, ModelInfo, ModelCapabilities
        
        ml = ModelList()
        ml.add(ModelInfo(
            id='vision-model',
            capabilities=ModelCapabilities(vision=True)
        ))
        ml.add(ModelInfo(
            id='text-model',
            capabilities=ModelCapabilities(vision=False)
        ))
        
        vision_models = ml.filter_by_capability('vision')
        assert len(vision_models) == 1
        assert vision_models[0].id == 'vision-model'


class TestLMStudioClient:
    """Тесты для LMStudioClient."""
    
    def test_client_creation(self):
        from lm_agent.api.lmstudio import LMStudioClient
        
        client = LMStudioClient(base_url='http://test:1234/v1', timeout=10)
        
        assert client.base_url == 'http://test:1234/v1'
        assert client.timeout == 10
    
    def test_client_default_url(self):
        from lm_agent.api.lmstudio import LMStudioClient
        
        client = LMStudioClient()
        
        assert 'localhost:1234' in client.base_url
    
    def test_client_cache_operations(self):
        from lm_agent.api.lmstudio import LMStudioClient
        
        client = LMStudioClient()
        client.set_cache_ttl(120)
        
        assert client._cache_ttl == 120
        
        client.clear_cache()
        assert client._models_cache is None


class TestRoleDefinition:
    """Тесты для RoleDefinition."""
    
    def test_role_creation(self):
        from lm_agent.core.roles import RoleDefinition, RoleCategory
        
        role = RoleDefinition(
            id='test_role',
            name='Test Role',
            description='A test role',
            category=RoleCategory.CUSTOM,
            system_prompt='You are a test role'
        )
        
        assert role.id == 'test_role'
        assert role.is_builtin is True
        assert role.temperature == 0.7
    
    def test_role_to_dict(self):
        from lm_agent.core.roles import RoleDefinition, RoleCategory
        
        role = RoleDefinition(
            id='test',
            name='Test',
            description='Desc',
            category=RoleCategory.DEVELOPMENT,
            system_prompt='Prompt'
        )
        
        d = role.to_dict()
        assert d['id'] == 'test'
        assert d['category'] == 'development'
        assert d['system_prompt'] == 'Prompt'
    
    def test_role_from_dict(self):
        from lm_agent.core.roles import RoleDefinition, RoleCategory
        
        data = {
            'id': 'imported',
            'name': 'Imported Role',
            'description': 'Desc',
            'category': 'testing',
            'system_prompt': 'Prompt here',
            'temperature': 0.5
        }
        
        role = RoleDefinition.from_dict(data)
        assert role.id == 'imported'
        assert role.category == RoleCategory.TESTING
        assert role.temperature == 0.5
    
    def test_role_build_messages(self):
        from lm_agent.core.roles import RoleDefinition, RoleCategory
        
        role = RoleDefinition(
            id='test',
            name='Test',
            description='Desc',
            category=RoleCategory.DEVELOPMENT,
            system_prompt='System prompt',
            examples=['Example task']
        )
        
        messages = role.build_messages('User task')
        
        assert len(messages) >= 3
        assert messages[0]['role'] == 'system'
        assert messages[-1]['role'] == 'user'
        assert messages[-1]['content'] == 'User task'


class TestRoleEngine:
    """Тесты для RoleEngine."""
    
    def test_engine_initialization(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        roles = engine.list_roles()
        
        assert len(roles) >= 7  # Встроенные роли
    
    def test_engine_list_roles_by_category(self):
        from lm_agent.core.roles import RoleEngine, RoleCategory
        
        engine = RoleEngine()
        
        dev_roles = engine.list_roles(category=RoleCategory.DEVELOPMENT)
        assert len(dev_roles) >= 2
        
        test_roles = engine.list_roles(category=RoleCategory.TESTING)
        assert len(test_roles) >= 1
    
    def test_engine_set_active_role(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        
        result = engine.set_active_role('code_generator')
        assert result is True
        
        active = engine.get_active_role()
        assert active is not None
        assert active.id == 'code_generator'
    
    def test_engine_set_invalid_role(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        
        result = engine.set_active_role('nonexistent_role')
        assert result is False
    
    def test_engine_get_system_prompt(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        engine.set_active_role('code_generator')
        
        prompt = engine.get_system_prompt()
        assert len(prompt) > 100
        assert 'Ты' in prompt or 'You' in prompt
    
    def test_engine_build_messages(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        engine.set_active_role('tester')
        
        messages = engine.build_messages('Write tests')
        
        assert len(messages) > 1
        assert messages[0]['role'] == 'system'
    
    def test_engine_get_recommendations(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        
        recs = engine.get_recommendations('напиши функцию для сортировки')
        assert len(recs) > 0
        
        # Первая рекомендация должна быть из категории development
        from lm_agent.core.roles import RoleCategory
        dev_roles = [r for r in recs if r.category == RoleCategory.DEVELOPMENT]
        assert len(dev_roles) > 0
    
    def test_engine_create_custom_role(self):
        from lm_agent.core.roles import RoleEngine, RoleCategory
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            engine = RoleEngine(custom_roles_path=temp_path)
            
            role = engine.create_custom_role(
                id='my_custom_role',
                name='My Custom Role',
                description='Custom description',
                system_prompt='Custom system prompt',
                category=RoleCategory.CUSTOM
            )
            
            assert role.id == 'my_custom_role'
            assert role.is_builtin is False
            
            # Проверка что роль сохранилась
            assert temp_path.exists()
            with open(temp_path) as f:
                data = json.load(f)
            assert len(data['roles']) == 1
            
        finally:
            temp_path.unlink()
    
    def test_engine_delete_custom_role(self):
        from lm_agent.core.roles import RoleEngine, RoleCategory
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            engine = RoleEngine(custom_roles_path=temp_path)
            
            engine.create_custom_role(
                id='to_delete',
                name='To Delete',
                description='Desc',
                system_prompt='Prompt',
                category=RoleCategory.CUSTOM
            )
            
            result = engine.delete_custom_role('to_delete')
            assert result is True
            
            # Нельзя удалить встроенную роль
            result = engine.delete_custom_role('code_generator')
            assert result is False
            
        finally:
            temp_path.unlink()
    
    def test_engine_cannot_delete_builtin(self):
        from lm_agent.core.roles import RoleEngine
        
        engine = RoleEngine()
        
        result = engine.delete_custom_role('code_generator')
        assert result is False


class TestRoleCategories:
    """Тесты для категорий ролей."""
    
    def test_all_categories_exist(self):
        from lm_agent.core.roles import RoleCategory
        
        categories = [c.value for c in RoleCategory]
        
        assert 'development' in categories
        assert 'analysis' in categories
        assert 'testing' in categories
        assert 'documentation' in categories
        assert 'security' in categories
        assert 'architecture' in categories
        assert 'custom' in categories


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
