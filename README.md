REST-XMPP-Client
================

HTTP-шлюз для работы с серверами xmpp

WEB-api
=========
#### Начало сесии 
`http://server.name/?jid=(user_jid)&password=(password)&server=(server)`

Ответ:

```
{"session": 
  {"session_id": "some_session_id"}
}
```
#### Информация о сессии
`http://server.name/sessions/some_sesion_id`

#### Список контактов
`http://server.name/sessions/some_sesion_id/contacts`

#### Информация о контакте
`http://server.name/sessions/some_sesion_id/contacts/contact_id`

#### Список сообщений
`http://server.name/sessions/some_sesion_id/contacts/contact_id/messages`

#### Отправка сообщения
`http://server.name/sessions/some_sesion_id/contacts/contact_id/messages?message=some_message_text`

Установка
=========
Шлюз оформлен в виде приложения для heroku, но может быть запущен и на любом другом сервере.
