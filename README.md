REST-XMPP-Client
================

HTTP-шлюз для работы с серверами xmpp

WEB-api
=========
#### Начало сесии 
- GET `http://server.name/auth/?jid=(user_jid)&password=(password)&server=(server)`
Ответ:
```
{"session": 
  {"session_id": "some_session_id"}
}
```

#### Информация о сессии
- GET `http://server.name/sessions/some_sesion_id`

#### Чаты сессии
- GET `http://server.name/sessions/some_sesion_id/chats`

#### Список контактов
- GET `http://server.name/sessions/some_sesion_id/contacts`

#### Информация о контакте
- GET `http://server.name/sessions/some_sesion_id/contacts/some_contact_id`

#### Чат контакта
- GET `http://server.name/sessions/some_sesion_id/contacts/some_contact_id/chat`

#### Добавления контакта
- GET `http://server.name/sessions/some_sesion_id/contacts?jid=some_jid`

#### Удаление контакта
- GET `http://server.name/sessions/some_sesion_id/contacts/some_contact_id/delete`
- DELETE `http://server.name/sessions/some_sesion_id/contacts/some_contact_id`

#### Авторизация контакта
- GET `http://server.name/sessions/some_sesion_id/contacts/some_contact_id/authorize`

#### Отправка сообщения
- Через сессию по jid - GET `http://server.name/sessions/some_sesion_id/messages?jid=some_jid&message=some_message_text`
- Через сессию по contact_id GET `http://server.name/sessions/some_sesion_id/messages?contact_id=contact_id&message=some_message_text`
- Через контакт - GET `http://server.name/sessions/some_sesion_id/contacts/some_contact_id/messages?message=some_message_text`

#### Завершение сессии
- GET `http://server.name/sessions/some_sesion_id/delete`
- DELETE `http://server.name/sessions/some_sesion_id`

Коды ошибок
=========
- 404 - Запрашиваемый ресурс не существует
- 400 - Не указаны обязательные параметры
- 502 - Ошибки xmpp соединения

Установка
=========
Шлюз оформлен в виде приложения для heroku, но может быть запущен и на любом другом сервере.
