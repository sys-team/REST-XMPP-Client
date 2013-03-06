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

#### Сообщения сессии
`http://server.name/sessions/some_sesion_id/messages`

#### Отправка сообщения
`http://server.name/sessions/some_sesion_id/messages?jid=some_contact_id&message=some_message_text`

#### Список контактов
`http://server.name/sessions/some_sesion_id/contacts`

#### Информация о контакте
`http://server.name/sessions/some_sesion_id/contacts/some_contact_id`


Установка
=========
Шлюз оформлен в виде приложения для heroku, но может быть запущен и на любом другом сервере.
