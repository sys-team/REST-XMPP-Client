REST-XMPP-Client
================

HTTP-шлюз для работы с серверами xmpp

Messaging-api
=========
#### Начало сесии 
- POST `/start-session`
- - Параметры:
- - - jid
- - - password
- - - server
- - - push_token (опционально)
Ответ:
```
{"session": 
  {"session_id": "some_session_id","jid":"some_jid","token":"access-token"}
}
```

## Авторизация запросов
Все запросы, кроме `/start-session` должны содержать хедэр `Authorization` со значением `Bearer access-token`.

`access-token` - токен, полученный в ответ на `/start-session`.

## Сессиия
- GET `/sessions/<session_id>` - информация о сессии
- DELETE `/sessions/some_sesion_id` или GET `/sessions/some_sesion_id/delete` - завершение сессии

#### Оповещение
- GET `/sessions/<session_id>/notification` - long polling запрос об изменениях, в случае наличия измений возвращает статус код 200

#### Сообщения
- GET `/sessions/<session_id>/messages` - все сообщения всех контактов сессии
- - Параметры:
- - - offset (опциональен) - возвращает все сообщения, timestap которых больше offset

#### Контакты
- GET `/sessions/<session_id>/contacts` - информация о контактах сессии
- - Параметры:
- - - offset (опциональен) - возвращает все контакты, timestap изменения которых больше offset

#### Лента
- GET `/sessions/<session_id>/feed` - информация о контактах сессии и сообщения сессии
- - Параметры:
- - - offset (опциональен) - возвращает все контакты, timestap изменения которых больше offset и все сообщения, timestap которых больше offset

## Контакт
- GET `/sessions/<session_id>/contacts/<contact_id>` - информация о контакте
- DELETE `/sessions/<session_id>/contacts/<contact_id>` или `/sessions/<session_id>/contacts/<contact_id>/delete` - удаление контакта
- GET `/sessions/<session_id>/contacts/<contact_id>/authorize` - авторизация контакта

#### Сообщения
- GET `/sessions/<session_id>/contacts/<contact_id>/messages` - сообщения контакта
- - Параметры:
- - - offset (опциональен) - возвращает все сообщения, timestap которых больше offset
- POST `/sessions/<session_id>/contacts/<contact_id>/messages`
- - Тело: ``` {'messages':{'text':'message_text'}}```
- - content-type = application/json


Statistics-api
=========
- GET `/server-status` - статистика количества открытых сессий, и занимаемой приложением памяти


Error codes
=========
- 400
- 401
- 404
- 500
- 502
