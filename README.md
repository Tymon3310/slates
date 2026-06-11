# Slates

Slates is a simple slack notes bot, built in python. It allows you to save, read and share your notes/snippets.

# Available commands

| Command | Arguments | Description |
| --- | --- | --- |
| /slates save | `note` | Add a new note. |
| /slates list |  | List all your notes. |
| /slates paste | `note_id` | Read a specific note. |
| /slates delete | `note_id` | Delete a specific note. |
| /slates share | `note_id` `@user` | Share a specific note with another user. |
| /slates unshare | `note_id` `@user` | Unshare a specific note with another user. |
| /slates-ping | `count` | Ping the bot a specified number of times (default 1, max 10). |
| /slates-help |  | Display help message. |