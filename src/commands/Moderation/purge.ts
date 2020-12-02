import { MessageEmbed, MessageEmbedOptions, TextChannel } from "discord.js";
import { FireMessage } from "../../../lib/extensions/message";
import { FireUser } from "../../../lib/extensions/user";
import { Language } from "../../../lib/util/language";
import { Command } from "../../../lib/util/command";
import { userConverter } from "../../../lib/util/converters";
import { argv } from "process";

export default class Purge extends Command {
  constructor() {
    super("purge", {
      description: (language: Language) =>
        language.get("PURGE_COMMAND_DESCRIPTION"),
      clientPermissions: ["SEND_MESSAGES", "MANAGE_MESSAGES"],
      userPermissions: ["MANAGE_MESSAGES"],
      args: [
        {
          id: "amount",
          type: "number",
          default: -1,
          required: true,
        },
        {
          id: "user",
          flag: "--user",
          match: "option",
          type: "user",
          default: null,
          required: false,
        },
        {
          id: "match",
          flag: "--match",
          match: "option",
          type: "string",
          required: false,
        },
        {
          id: "nomatch",
          flag: "--nomatch",
          match: "option",
          type: "string",
          required: false,
        },
        {
          id: "includeEmbeds",
          flag: "--include_embeds",
          match: "flag",
          required: false,
        },
        {
          id: "startsWith",
          flag: "--startswith",
          match: "option",
          type: "string",
          required: false,
        },
        {
          id: "endsWith",
          flag: "--endswith",
          match: "option",
          type: "string",
          required: false,
        },
        {
          id: "attachments",
          flag: "--attachments",
          match: "flag",
          required: false,
        },
        {
          id: "bot",
          flag: "--bot",
          match: "flag",
          required: false,
        },
        {
          id: "reason",
          flag: "--reason",
          match: "option",
          type: "string",
          required: false,
        },
      ],
    });
  }

  async exec(
    message: FireMessage,
    args: {
      amount: number;
      user?: FireUser;
      match?: string;
      nomatch?: string;
      includeEmbeds?: string;
      startsWith?: string;
      endsWith?: string;
      attachments?: string;
      bot?: string;
      reason?: string;
    }
  ) {
    if (args.amount > 100 || args.amount <= 1)
      return await message.error("PURGE_AMOUNT_INVALID");
    message.delete().catch(() => {});
    if (
      args.user ||
      args.match ||
      args.nomatch ||
      args.includeEmbeds ||
      args.startsWith ||
      args.endsWith ||
      args.attachments ||
      args.bot
    )
      await this.flagPurge(message, args);
    else await this.basicPurge(message, args.amount);
  }

  getEmbedContent(embed: MessageEmbed | MessageEmbedOptions) {
    let content = [embed.title, embed.description];
    embed?.fields.forEach((field) =>
      content.push(`${field.name} ${field.value}`)
    );
    if (embed?.footer?.text) content.push(embed.footer.text);
    if (embed?.author?.name) content.push(embed.author.name);
    return content.join("");
  }

  async basicPurge(message: FireMessage, amount: number) {
    let recentPurge = [];
    try {
      (await message.channel.messages.fetch({ limit: amount })).forEach(
        (fetchedMessage: FireMessage) => {
          if (fetchedMessage.id != message.id)
            recentPurge.push({
              author: fetchedMessage.author.toJSON(),
              content: fetchedMessage.cleanContent,
              embeds: [...fetchedMessage.embeds.map((embed) => embed.toJSON())],
              attachments: [
                ...fetchedMessage.attachments.map((attachment) =>
                  attachment.toJSON()
                ),
              ],
            });
        }
      );
    } catch {
      recentPurge.push({ error: message.language.get("PURGE_HISTORY_FAIL") });
    }
    try {
      (message.channel as TextChannel)
        .bulkDelete(amount, true)
        .then(async (messages) => {
          this.client.emit("purge", message, null, recentPurge);
          return message
            .success("PURGE_SUCCESS", messages.size)
            .then((message: FireMessage) => message.delete({ timeout: 5000 }));
        });
    } catch {
      return await message.error("PURGE_FAIL");
    }
  }

  async flagPurge(
    message: FireMessage,
    args: {
      amount: number;
      user?: FireUser;
      match?: string;
      nomatch?: string;
      includeEmbeds?: string;
      startsWith?: string;
      endsWith?: string;
      attachments?: string;
      bot?: string;
      reason?: string;
    }
  ) {
    const filter = (message: FireMessage) => {
      let content = message.content.toLowerCase();
      if (args.includeEmbeds && message.embeds.length)
        content += message.embeds
          .map((embed) => this.getEmbedContent(embed).toLowerCase())
          .join("");
      let completed: boolean[] = [];
      if (args.user) completed.push(args.user?.id == message.author.id);
      if (args.match)
        completed.push(content.includes(args.match.toLowerCase()));
      if (args.nomatch)
        completed.push(!content.includes(args.nomatch.toLowerCase()));
      if (args.startsWith)
        completed.push(content.startsWith(args.startsWith.toLowerCase()));
      if (args.endsWith)
        completed.push(content.endsWith(args.endsWith.toLowerCase()));
      if (args.attachments) completed.push(message.attachments.size >= 1);
      if (args.bot) completed.push(message.author.bot);
      return completed.filter((c) => !c).length == 0;
    };
    let recentPurge = [],
      messages: FireMessage[] = [];
    try {
      (await message.channel.messages.fetch({ limit: args.amount }))
        .filter((message: FireMessage) => filter(message))
        .forEach((fetchedMessage: FireMessage) => {
          if (fetchedMessage.id != message.id) {
            messages.push(fetchedMessage);
            recentPurge.push({
              author: fetchedMessage.author.toJSON(),
              content: fetchedMessage.cleanContent,
              embeds: [...fetchedMessage.embeds.map((embed) => embed.toJSON())],
              attachments: [
                ...fetchedMessage.attachments.map((attachment) =>
                  attachment.toJSON()
                ),
              ],
            });
          }
        });
    } catch {
      recentPurge.push({ error: message.language.get("PURGE_HISTORY_FAIL") });
    }
    if (!recentPurge.length || !messages.length) return;
    try {
      (message.channel as TextChannel)
        .bulkDelete(messages, true)
        .then(async (messages) => {
          this.client.emit("purge", message, args.reason, recentPurge);
          return message
            .success("PURGE_SUCCESS", messages.size)
            .then((message: FireMessage) => message.delete({ timeout: 5000 }));
        });
    } catch {
      return await message.error("PURGE_FAIL");
    }
  }
}