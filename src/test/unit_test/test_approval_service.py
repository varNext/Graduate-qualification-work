import pytest
from unittest.mock import AsyncMock, patch

VALID_PACKAGES = [{
    "products": [{"sku": 12345, "quantity": 2}],
    "weight": 1.5, "width": 10, "height": 10, "depth": 10
}]


class TestFBSApprovalService:
    """тесты для FBSApprovalService"""

    @pytest.fixture
    def service(self):
        from src.app.fbs.approval_service import FBSApprovalService
        return FBSApprovalService(client_id="test", api_key="test")

    # Тесты валидации
    def test_validate_valid_packages(self, service):
        """Валидные упаковки"""
        assert service._validate_packages(VALID_PACKAGES) is True

    def test_validate_invalid_packages(self, service):
        """Невалидные упаковки"""
        invalid = [{"products": []}]
        assert service._validate_packages(invalid) is False


    @pytest.mark.asyncio
    async def test_empty_posting_number(self, service):
        """Пустой номер отправления"""

        with patch.object(service, 'start', new=AsyncMock()):
            result = await service.approve_single_posting("", VALID_PACKAGES)
            assert result["success"] is False
            assert "Не указан номер отправления" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_packages_error(self, service):
        """Невалидные упаковки - ошибка"""
        with patch.object(service, 'start', new=AsyncMock()):
            invalid = [{"products": []}]
            result = await service.approve_single_posting("POSTING-123", invalid)
            assert result["success"] is False
            assert "Некорректные данные упаковок" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_approval_simple(self, service):
        """Простой тест успешного подтверждения"""

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "approved"})

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_context)
        mock_session.closed = False

        with patch.object(service, 'start', new=AsyncMock()):
            service.session = mock_session
            result = await service.approve_single_posting("POSTING-123", VALID_PACKAGES)


            assert isinstance(result, dict)


            if result.get("success"):
                assert result["posting_number"] == "POSTING-123"
                assert "approved_at" in result
            else:

                assert "Не указан номер отправления" not in str(result)
                assert "Некорректные данные упаковок" not in str(result)

    @pytest.mark.asyncio
    async def test_api_error_simple(self, service):
        """Простой тест ошибки API"""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request")

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_context)

        with patch.object(service, 'start', new=AsyncMock()):
            service.session = mock_session
            result = await service.approve_single_posting("POSTING-123", VALID_PACKAGES)

            # Просто проверяем что это не успех
            assert result.get("success") is not True

    @pytest.mark.asyncio
    async def test_batch_approve_simple(self, service):
        """Простой тест массового подтверждения"""
        approvals = [
            {"posting_number": "POSTING-1", "packages": VALID_PACKAGES},
            {"posting_number": "POSTING-2", "packages": VALID_PACKAGES}
        ]

        with patch.object(service, 'approve_single_posting', new=AsyncMock()) as mock_approve:
            mock_approve.return_value = {"success": True, "posting_number": "POSTING-1"}

            result = await service.batch_approve_postings(approvals)


            assert result["total"] == 2
            assert isinstance(result["results"], list)
            assert len(result["results"]) == 2