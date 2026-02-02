import asyncio
import logging
import os
from datetime import datetime

import docker
from docker.errors import NotFound, APIError, ImageNotFound

logger = logging.getLogger(__name__)

IMAGE_NAME = "telegram-gift-bot"
DOCKERFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "Telegram-Bot-NFT")
CONTAINER_PREFIX = "nft-bot-"
DATA_BASE_DIR = os.path.join(os.path.dirname(__file__), "data", "users")
MAX_RESTART_ATTEMPTS = 3

# Счётчик перезапусков: {telegram_id: count}
_restart_counts: dict[int, int] = {}


def _get_client() -> docker.DockerClient:
    return docker.from_env()


def _container_name(telegram_id: int) -> str:
    return f"{CONTAINER_PREFIX}{telegram_id}"


async def build_image_if_needed() -> bool:
    """Проверить наличие образа, при необходимости собрать."""
    def _build():
        try:
            client = _get_client()
        except Exception as e:
            logger.warning(f"Docker недоступен, пропускаю проверку образа: {e}")
            return False
        try:
            client.images.get(IMAGE_NAME)
            logger.info(f"Docker-образ '{IMAGE_NAME}' уже существует")
            return True
        except ImageNotFound:
            logger.info(f"Docker-образ '{IMAGE_NAME}' не найден, собираю...")
            try:
                client.images.build(
                    path=DOCKERFILE_PATH,
                    dockerfile="docker/Dockerfile",
                    tag=IMAGE_NAME,
                    rm=True,
                )
                logger.info(f"Docker-образ '{IMAGE_NAME}' успешно собран")
                return True
            except Exception as e:
                logger.error(f"Ошибка сборки образа: {e}")
                return False
        except Exception as e:
            logger.warning(f"Ошибка проверки Docker-образа: {e}")
            return False
        finally:
            client.close()

    return await asyncio.get_event_loop().run_in_executor(None, _build)


UDP_PORT_BASE = int(os.getenv("UDP_PORT_BASE", "9200"))


async def start_container(
    telegram_id: int,
    bot_token: str,
    license_key: str,
    session_string: str = "",
    udp_port: int = 0,
) -> str | None:
    """Создать и запустить контейнер для пользователя. Возвращает container_id или None."""
    def _start():
        client = _get_client()
        name = _container_name(telegram_id)

        # Удалить старый контейнер, если есть
        try:
            old = client.containers.get(name)
            old.stop(timeout=10)
            old.remove(force=True)
        except NotFound:
            pass
        except Exception as e:
            logger.warning(f"Ошибка при удалении старого контейнера {name}: {e}")

        user_data_dir = os.path.join(DATA_BASE_DIR, str(telegram_id))
        os.makedirs(user_data_dir, exist_ok=True)

        container_udp_port = udp_port or (UDP_PORT_BASE + (telegram_id % 1000))

        env = {
            "BOT_TOKEN": bot_token,
            "ADMIN_ID": str(telegram_id),
            "LICENSE_KEY": license_key,
            "API_ID": os.getenv("SERVER_API_ID", ""),
            "API_HASH": os.getenv("SERVER_API_HASH", ""),
            "SESSION_STRING": session_string,
            "UDP_LISTEN_PORT": str(container_udp_port),
            "TZ": "Europe/Moscow",
        }

        try:
            container = client.containers.run(
                IMAGE_NAME,
                name=name,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                environment=env,
                volumes={
                    os.path.abspath(user_data_dir): {"bind": "/app/data", "mode": "rw"}
                },
                ports={f"{container_udp_port}/udp": container_udp_port},
            )
            logger.info(f"Контейнер {name} запущен: {container.id}, UDP порт: {container_udp_port}")
            _restart_counts.pop(telegram_id, None)
            return container.id
        except Exception as e:
            logger.error(f"Ошибка запуска контейнера {name}: {e}")
            return None
        finally:
            client.close()

    return await asyncio.get_event_loop().run_in_executor(None, _start)


async def stop_container(telegram_id: int) -> bool:
    """Остановить контейнер пользователя."""
    def _stop():
        client = _get_client()
        try:
            container = client.containers.get(_container_name(telegram_id))
            container.stop(timeout=10)
            logger.info(f"Контейнер {_container_name(telegram_id)} остановлен")
            return True
        except NotFound:
            logger.warning(f"Контейнер {_container_name(telegram_id)} не найден")
            return False
        except Exception as e:
            logger.error(f"Ошибка остановки контейнера: {e}")
            return False
        finally:
            client.close()

    return await asyncio.get_event_loop().run_in_executor(None, _stop)


async def restart_container(telegram_id: int) -> bool:
    """Перезапустить контейнер пользователя."""
    def _restart():
        client = _get_client()
        try:
            container = client.containers.get(_container_name(telegram_id))
            container.restart(timeout=10)
            logger.info(f"Контейнер {_container_name(telegram_id)} перезапущен")
            return True
        except NotFound:
            logger.warning(f"Контейнер {_container_name(telegram_id)} не найден")
            return False
        except Exception as e:
            logger.error(f"Ошибка перезапуска контейнера: {e}")
            return False
        finally:
            client.close()

    return await asyncio.get_event_loop().run_in_executor(None, _restart)


async def remove_container(telegram_id: int) -> bool:
    """Остановить и удалить контейнер пользователя."""
    def _remove():
        client = _get_client()
        try:
            container = client.containers.get(_container_name(telegram_id))
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Контейнер {_container_name(telegram_id)} удалён")
            _restart_counts.pop(telegram_id, None)
            return True
        except NotFound:
            logger.warning(f"Контейнер {_container_name(telegram_id)} не найден для удаления")
            _restart_counts.pop(telegram_id, None)
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления контейнера: {e}")
            return False
        finally:
            client.close()

    return await asyncio.get_event_loop().run_in_executor(None, _remove)


async def get_container_status(telegram_id: int) -> str:
    """Получить статус контейнера: running / stopped / not_found."""
    def _status():
        client = _get_client()
        try:
            container = client.containers.get(_container_name(telegram_id))
            return container.status  # running, exited, paused, etc.
        except NotFound:
            return "not_found"
        except Exception as e:
            logger.error(f"Ошибка получения статуса контейнера: {e}")
            return "not_found"
        finally:
            client.close()

    status = await asyncio.get_event_loop().run_in_executor(None, _status)
    if status == "exited":
        return "stopped"
    return status


async def get_container_logs(telegram_id: int, lines: int = 50) -> str:
    """Получить последние N строк логов контейнера."""
    def _logs():
        client = _get_client()
        try:
            container = client.containers.get(_container_name(telegram_id))
            logs = container.logs(tail=lines, timestamps=False).decode("utf-8", errors="replace")
            return logs if logs.strip() else "(логи пусты)"
        except NotFound:
            return "(контейнер не найден)"
        except Exception as e:
            logger.error(f"Ошибка получения логов: {e}")
            return f"(ошибка: {e})"
        finally:
            client.close()

    return await asyncio.get_event_loop().run_in_executor(None, _logs)


async def monitor_containers(db, bot):
    """Фоновая задача мониторинга контейнеров.

    Каждые 60 сек:
    - Проверяет всех Hosting-пользователей с deployment_status='running'
    - Если контейнер упал — перезапускает (max 3 раза)
    - Если подписка истекла — останавливает и удаляет контейнер
    """
    while True:
        try:
            hosting_users = db.get_hosting_users()
            for user_row in hosting_users:
                telegram_id = user_row[1]
                subscription_end = user_row[5]

                # Проверяем истечение подписки
                if subscription_end:
                    try:
                        end_dt = datetime.fromisoformat(subscription_end)
                        if end_dt <= datetime.now():
                            logger.info(f"Подписка истекла у {telegram_id}, останавливаю контейнер")
                            await remove_container(telegram_id)
                            db.update_deployment_status(telegram_id, "stopped")
                            db.update_container_id(telegram_id, None)
                            try:
                                from aiogram.enums import ParseMode
                                await bot.send_message(
                                    telegram_id,
                                    "⚠️ <b>Подписка истекла</b>\n\n"
                                    "Ваш бот был остановлен. Продлите подписку для возобновления работы.",
                                    parse_mode=ParseMode.HTML,
                                )
                            except Exception:
                                pass
                            continue
                    except (ValueError, TypeError):
                        pass

                # Проверяем статус контейнера
                status = await get_container_status(telegram_id)
                if status != "running":
                    count = _restart_counts.get(telegram_id, 0)
                    if count < MAX_RESTART_ATTEMPTS:
                        logger.warning(
                            f"Контейнер {_container_name(telegram_id)} не запущен "
                            f"(статус: {status}), попытка перезапуска {count + 1}/{MAX_RESTART_ATTEMPTS}"
                        )
                        success = await restart_container(telegram_id)
                        _restart_counts[telegram_id] = count + 1
                        if not success:
                            logger.error(f"Не удалось перезапустить контейнер для {telegram_id}")
                    else:
                        logger.error(
                            f"Контейнер {_container_name(telegram_id)} не запускается "
                            f"после {MAX_RESTART_ATTEMPTS} попыток, помечаю как stopped"
                        )
                        db.update_deployment_status(telegram_id, "stopped")
                        _restart_counts.pop(telegram_id, None)
                        try:
                            from aiogram.enums import ParseMode
                            await bot.send_message(
                                telegram_id,
                                "⚠️ <b>Проблема с ботом</b>\n\n"
                                "Ваш бот был остановлен из-за повторных сбоев. "
                                "Проверьте настройки и перезапустите через меню управления.",
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass
                else:
                    # Контейнер работает — сбрасываем счётчик
                    _restart_counts.pop(telegram_id, None)

        except Exception as e:
            logger.error(f"Ошибка в monitor_containers: {e}")

        await asyncio.sleep(60)
