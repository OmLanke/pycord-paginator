from __future__ import annotations
from collections.abc import Mapping
from typing import overload, TYPE_CHECKING

import discord

from .buttons import PaginatorButton, PaginatorButtonType, PaginatorMenu
from .pages import Page, PageGroup

if TYPE_CHECKING:
    from discord.ext.bridge import (
        Context as BridgeContext,
        BridgeExtContext,
        BridgeApplicationContext,
    )

__all__ = ("Paginator",)

# TODO: Try to use EAFP style


class Paginator(discord.ui.View, Mapping):
    """Creates a paginator which can be sent as a message and uses buttons for navigation.

    Parameters
    ----------
    pages: Union[List[:class:`PageGroup`], List[:class:`Page`], List[:class:`str`], List[Union[List[:class:`discord.Embed`], :class:`discord.Embed`]]]
        The list of :class:`PageGroup` objects, :class:`Page` objects, strings, embeds, or list of embeds to paginate.
        If a list of :class:`PageGroup` objects is provided and `show_menu` is ``False``,
        only the first page group will be displayed.
    show_disabled: :class:`bool`
        Whether to show disabled buttons.
    show_indicator: :class:`bool`
        Whether to show the page indicator when using the default buttons.
    show_menu: :class:`bool`
        Whether to show a select menu that allows the user to switch between groups of pages.
    menu_placeholder: :class:`str`
        The placeholder text to show in the page group menu when no page group has been selected yet.
        Defaults to "Select Page Group" if not provided.
    author_check: :class:`bool`
        Whether only the original user of the command can change pages.
    disable_on_timeout: :class:`bool`
        Whether the buttons get disabled when the paginator view times out.
    use_default_buttons: :class:`bool`
        Whether to use the default buttons (i.e. ``first``, ``prev``, ``page_indicator``, ``next``, ``last``)
    default_button_row: :class:`int`
        The row where the default paginator buttons are displayed. Has no effect if custom buttons are used.
    loop_pages: :class:`bool`
        Whether to loop the pages when clicking prev/next while at the first/last page in the list.
    custom_view: Optional[:class:`discord.ui.View`]
        A custom view whose items are appended below the pagination components.
        If the currently displayed page has a `custom_view` assigned, it will replace these
        view components when that page is displayed.
    timeout: Optional[:class:`float`]
        Timeout in seconds from last interaction with the paginator before no longer accepting input.
    custom_buttons: Optional[List[:class:`PaginatorButton`]]
        A list of PaginatorButtons to initialize the Paginator with.
        If ``use_default_buttons`` is ``True``, this parameter is ignored.
    trigger_on_display: :class:`bool`
        Whether to automatically trigger the callback associated with a `Page` whenever it is displayed.
        Has no effect if no callback exists for a `Page`.

    Attributes
    ----------
    menu: Optional[List[:class:`PaginatorMenu`]]
        The page group select menu associated with this paginator.
    page_groups: Optional[List[:class:`PageGroup`]]
        List of :class:`PageGroup` objects the user can switch between.
    default_page_group: Optional[:class:`int`]
        The index of the default page group shown when the paginator is initially sent.
        Defined by setting ``default`` to ``True`` on a :class:`PageGroup`.
    current_page: :class:`int`
        A zero-indexed value showing the current page number.
    page_count: :class:`int`
        A zero-indexed value showing the total number of pages.
    buttons: Dict[:class:`str`, Dict[:class:`str`, Union[:class:`~PaginatorButton`, :class:`bool`]]]
        A dictionary containing the :class:`~PaginatorButton` objects included in this paginator.
    user: Optional[Union[:class:`~discord.User`, :class:`~discord.Member`]]
        The user or member that invoked the paginator.
    message: Union[:class:`~discord.Message`, :class:`~discord.WebhookMessage`]
        The message the paginator is attached to.
    """

    def __init__(
        self,
        pages: (
            list[Page]
            | list[str]
            | list[list[discord.Embed]]
            | list[discord.Embed]
            | list[PageGroup]
        ),
        show_disabled: bool = True,
        show_indicator=True,
        show_menu=False,
        menu_placeholder: str = "Select Page Group",
        author_check=False,
        disable_on_timeout=True,
        use_default_buttons=True,
        default_button_row: int = 0,
        loop_pages=False,
        custom_view: discord.ui.View | None = None,
        timeout: float | None = 180.0,
        custom_buttons: list[PaginatorButton] | None = None,
        trigger_on_display: bool | None = None,
        users: set[discord.User | discord.Member] | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.timeout: float | None = timeout
        self.pages: (
            list[str]
            | list[Page]
            | list[discord.Embed]
            | list[list[discord.Embed]]
            | list[PageGroup]
        ) = pages
        self.current_page = 0
        self.menu: PaginatorMenu | None = None
        self.show_menu = show_menu
        self.menu_placeholder = menu_placeholder
        self.page_groups: list[PageGroup] | None = None
        self.default_page_group: int = 0

        all_groups = True
        default_group = None

        for pg in self.pages:
            if not isinstance(pg, PageGroup):
                all_groups = False
                break

            if pg.default:
                if default_group is not None:
                    raise ValueError("Only one PageGroup can be set as the default.")
                default_group = pg

        if all_groups:
            self.page_groups = self.pages if show_menu else []  # type: ignore # all_groups is True, so self.page_groups is a list[PageGroup]
            self.default_page_group = self.page_groups.index(default_group)
            self.pages: list[Page] = self.get_page_group_content(
                self.page_groups[self.default_page_group]
            )

        self.page_count = max(len(self.pages) - 1, 0)
        self.buttons: dict[PaginatorButtonType, PaginatorButton] = {}
        self.custom_buttons: list[PaginatorButton] | None = custom_buttons
        self.show_disabled = show_disabled
        self.show_indicator = show_indicator
        self.disable_on_timeout = disable_on_timeout
        self.use_default_buttons = use_default_buttons
        self.default_button_row = default_button_row
        self.loop_pages = loop_pages
        self.custom_view: discord.ui.View | None = custom_view
        self.trigger_on_display = trigger_on_display
        self.message: discord.Message | discord.WebhookMessage | None = None

        if self.custom_buttons is not None and not self.use_default_buttons:
            for button in self.custom_buttons:
                self.add_button(button)
        elif not self.custom_buttons and self.use_default_buttons:
            self.add_default_buttons()

        if self.show_menu:
            self.add_menu()

        self.usercheck = author_check
        self.users = users

    # In order to support the Mapping protocol, we need to implement these 3 methods
    # This allows us to unpack paginator in the kwargs of a send function. Example:
    # await channel.send(**paginator)
    def __getitem__(self, key):
        return self._prepare()[key]

    def __iter__(self):
        return iter(self._prepare())

    def __len__(self):
        return len(self._prepare())

    async def update(
        self,
        pages: None
        | (
            list[PageGroup]
            | list[Page]
            | list[str]
            | list[list[discord.Embed]]
            | list[discord.Embed]
        ) = None,
        show_disabled: bool | None = None,
        show_indicator: bool | None = None,
        show_menu: bool | None = None,
        author_check: bool | None = None,
        menu_placeholder: str | None = None,
        disable_on_timeout: bool | None = None,
        use_default_buttons: bool | None = None,
        default_button_row: int | None = None,
        loop_pages: bool | None = None,
        custom_view: discord.ui.View | None = discord.MISSING,
        timeout: float | None = discord.MISSING,
        custom_buttons: list[PaginatorButton] | None = discord.MISSING,
        trigger_on_display: bool | None = None,
        interaction: discord.Interaction | None = None,
        current_page: int = 0,
        users: set[discord.User | discord.Member] | None = discord.MISSING,
    ):
        """Updates the existing :class:`Paginator` instance with the provided options.

        Parameters
        ----------
        pages: Optional[Union[List[:class:`PageGroup`], List[:class:`Page`], List[:class:`str`], List[Union[List[:class:`discord.Embed`], :class:`discord.Embed`]]]]
            The list of :class:`PageGroup` objects, :class:`Page` objects, strings,
            embeds, or list of embeds to paginate.
        show_disabled: :class:`bool`
            Whether to show disabled buttons.
        show_indicator: :class:`bool`
            Whether to show the page indicator when using the default buttons.
        show_menu: :class:`bool`
            Whether to show a select menu that allows the user to switch between groups of pages.
        author_check: :class:`bool`
            Whether only the original user of the command can change pages.
        menu_placeholder: :class:`str`
            The placeholder text to show in the page group menu when no page group has been selected yet.
            Defaults to "Select Page Group" if not provided.
        disable_on_timeout: :class:`bool`
            Whether the buttons get disabled when the paginator view times out.
        use_default_buttons: :class:`bool`
            Whether to use the default buttons (i.e. ``first``, ``prev``, ``page_indicator``, ``next``, ``last``)
        default_button_row: Optional[:class:`int`]
            The row where the default paginator buttons are displayed. Has no effect if custom buttons are used.
        loop_pages: :class:`bool`
            Whether to loop the pages when clicking prev/next while at the first/last page in the list.
        custom_view: Optional[:class:`discord.ui.View`]
            A custom view whose items are appended below the pagination components.
        timeout: Optional[:class:`float`]
            Timeout in seconds from last interaction with the paginator before no longer accepting input.
        custom_buttons: Optional[List[:class:`PaginatorButton`]]
            A list of PaginatorButtons to initialize the Paginator with.
            If ``use_default_buttons`` is ``True``, this parameter is ignored.
        trigger_on_display: :class:`bool`
            Whether to automatically trigger the callback associated with a `Page` whenever it is displayed.
            Has no effect if no callback exists for a `Page`.
        interaction: Optional[:class:`discord.Interaction`]
            The interaction to use when updating the paginator. If not provided, the paginator will be updated
            by using its stored :attr:`message` attribute instead.
        current_page: :class:`int`
            The initial page number to display when updating the paginator.
        """

        # Update pages and reset current_page to 0 (default)
        self.pages = pages or self.pages
        self.show_menu = show_menu if show_menu is not None else self.show_menu

        if pages is not None:

            all_groups = True
            default_group: PageGroup | None = None

            for pg in pages:
                if not isinstance(pg, PageGroup):
                    all_groups = False
                    break

                if pg.default:
                    if default_group is not None:
                        raise ValueError(
                            "Only one PageGroup can be set as the default."
                        )
                    default_group = pg

            if all_groups:
                self.page_groups = self.pages if show_menu else []  # type: ignore # all_groups is True, so self.page_groups is a list[PageGroup]
                self.default_page_group = self.page_groups.index(default_group)
                self.pages: list[Page] = self.get_page_group_content(
                    self.page_groups[self.default_page_group]
                )

        self.page_count = max(len(self.pages) - 1, 0)
        self.current_page = current_page if current_page <= self.page_count else 0
        # Apply config changes, if specified
        if show_disabled is not None:
            self.show_disabled = show_disabled
        if show_indicator is not None:
            self.show_indicator = show_indicator
        if author_check is not None:
            self.usercheck = author_check
        if menu_placeholder is not None:
            self.menu_placeholder = menu_placeholder
        if disable_on_timeout is not None:
            self.disable_on_timeout = disable_on_timeout
        if use_default_buttons is not None:
            self.use_default_buttons = use_default_buttons
        if default_button_row is not None:
            self.default_button_row = default_button_row
        if loop_pages is not None:
            self.loop_pages = loop_pages
        if custom_view is not None:
            self.custom_view = custom_view
        if timeout is not discord.MISSING:
            self.timeout = timeout
        if trigger_on_display is not None:
            self.trigger_on_display = trigger_on_display
        if users is not discord.MISSING:
            self.users = users
        if custom_buttons is not discord.MISSING:
            self.custom_buttons = custom_buttons

        if self.use_default_buttons == True:
            self.buttons.clear()
            self.add_default_buttons()
        else:
            if self.custom_buttons is not None:
                self.buttons.clear()
                for button in self.custom_buttons:
                    self.add_button(button)

        await self.goto_page(self.current_page, interaction=interaction)

    async def on_timeout(self) -> None:
        """Disables all buttons when the view times out."""
        if self.disable_on_timeout:
            for item in self.children:
                item.disabled = True
            page = self.pages[self.current_page]
            page = self.get_page_content(page)
            files = page.update_files()
            try:
                await self.message.edit(
                    view=self,
                    files=files or [],
                    attachments=[],
                )
            except (discord.NotFound, discord.Forbidden):
                pass
        self.stop()

    async def disable(
        self,
        include_custom: bool = False,
        page: None | (str | Page | list[discord.Embed] | discord.Embed) = None,
    ) -> None:
        """Stops the paginator, disabling all of its components.

        Parameters
        ----------
        include_custom: :class:`bool`
            Whether to disable components added via custom views.
        page: Optional[Union[:class:`str`, Union[List[:class:`discord.Embed`], :class:`discord.Embed`]]]
            The page content to show after disabling the paginator.
        """
        page = self.get_page_content(page)
        for item in self.children:
            if (
                include_custom
                or not self.custom_view
                or item not in self.custom_view.children
            ):
                item.disabled = True
        if page:
            await self.message.edit(
                content=page.content,
                embeds=page.embeds,
                view=self,
            )
        else:
            await self.message.edit(view=self)

    async def cancel(
        self,
        include_custom: bool = False,
        page: None | str | Page | list[discord.Embed] | discord.Embed = None,
    ) -> None:
        """Cancels the paginator, removing all of its components from the message.

        Parameters
        ----------
        include_custom: :class:`bool`
            Whether to remove components added via custom views.
        page: Optional[Union[:class:`str`, Union[List[:class:`discord.Embed`], :class:`discord.Embed`]]]
            The page content to show after canceling the paginator.
        """
        items = self.children.copy()
        page = self.get_page_content(page)
        for item in items:
            if (
                include_custom
                or not self.custom_view
                or item not in self.custom_view.children
            ):
                self.remove_item(item)
        if page:
            await self.message.edit(
                content=page.content,
                embeds=page.embeds,
                view=self,
            )
        else:
            await self.message.edit(view=self)

    def _prepare(self, update_files: bool = False):
        """Prepares the paginator for sending by updating the display state of the buttons."""
        self.update_buttons()
        page = self.pages[self.current_page]
        page_content = self.get_page_content(page)

        if page_content.custom_view:
            self.update_custom_view(page_content.custom_view)

        if update_files:
            page_content.update_files()

        return {
            "content": page_content.content,
            "embeds": page_content.embeds,
            "files": page_content.files,
            "view": self,
        }

    async def goto_page(
        self, page_number: int = 0, *, interaction: discord.Interaction | None = None
    ) -> None:
        """Updates the paginator message to show the specified page number.

        Parameters
        ----------
        page_number: :class:`int`
            The page to display.

            .. note::

                Page numbers are zero-indexed when referenced internally,
                but appear as one-indexed when shown to the user.

        interaction: Optional[:class:`discord.Interaction`]
            The interaction to use when editing the message. If not provided, the message will be
            edited using the paginator's stored :attr:`message` attribute instead.

        Returns
        -------
        :class:`~discord.Message`
            The message associated with the paginator.
        """
        self.current_page = page_number
        self._prepare(True)

        if interaction:
            await interaction.response.defer()  # needed to force webhook message edit route for files kwarg support # TODO: Check if this is still needed
            await interaction.followup.edit_message(
                message_id=self.message.id,
                **self,
                attachments=[],
            )
        else:
            await self.message.edit(
                **self,
                attachments=[],
            )
        if self.trigger_on_display:
            await self.page_action(interaction=interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.usercheck:
            return interaction.user in self.users
        return True

    def add_menu(self):
        """Adds the default :class:`PaginatorMenu` instance to the paginator."""
        self.menu = PaginatorMenu(self.page_groups, placeholder=self.menu_placeholder)
        self.menu.paginator = self
        self.add_item(self.menu)

    def add_default_buttons(self):
        """Adds the full list of default buttons that can be used with the paginator.
        Includes ``first``, ``prev``, ``page_indicator``, ``next``, and ``last``.
        """
        default_buttons = [
            PaginatorButton(
                PaginatorButtonType.first,
                label="<<",
                style=discord.ButtonStyle.blurple,
                row=self.default_button_row,
            ),
            PaginatorButton(
                PaginatorButtonType.prev,
                label="<",
                style=discord.ButtonStyle.red,
                loop_label="↪",
                row=self.default_button_row,
            ),
            PaginatorButton(
                PaginatorButtonType.page_indicator,
                style=discord.ButtonStyle.gray,
                disabled=True,
                row=self.default_button_row,
            ),
            PaginatorButton(
                PaginatorButtonType.next,
                label=">",
                style=discord.ButtonStyle.green,
                loop_label="↩",
                row=self.default_button_row,
            ),
            PaginatorButton(
                PaginatorButtonType.last,
                label=">>",
                style=discord.ButtonStyle.blurple,
                row=self.default_button_row,
            ),
        ]
        for button in default_buttons:
            self.add_button(button)

    def add_button(self, button: PaginatorButton):
        """Adds a :class:`PaginatorButton` to the paginator."""
        if button.button_type == PaginatorButtonType.page_indicator:
            button.hidden = self.show_indicator
            if button.label is None and button.emoji is None:
                button.label = f"{self.current_page + 1}/{self.page_count + 1}"

        button.paginator = self

        self.buttons[button.button_type] = button

    def remove_button(self, button_type: PaginatorButtonType):
        """Removes a :class:`PaginatorButton` from the paginator."""
        if button_type not in self.buttons.keys():
            raise ValueError(
                f"no button_type {button_type} was found in this paginator."
            )
        return self.buttons.pop(button_type)

    def update_buttons(self) -> dict:
        """Updates the display state of the buttons (disabled/hidden)

        Returns
        -------
        Dict[:class:`str`, Dict[:class:`str`, Union[:class:`~PaginatorButton`, :class:`bool`]]]
            The dictionary of buttons that were updated.
        """

        self.buttons[PaginatorButtonType.first].hidden = self.current_page <= 1
        self.buttons[PaginatorButtonType.last].hidden = (
            self.current_page >= self.page_count - 1
        )
        next_button = self.buttons[PaginatorButtonType.next]
        if self.current_page == self.page_count:
            if not self.loop_pages:
                next_button.hidden = True
                next_button.label = next_button._label
            else:
                next_button.label = next_button.loop_label
        elif self.current_page < self.page_count:
            next_button.hidden = False
            next_button.label = next_button._label

        prev_button = self.buttons[PaginatorButtonType.prev]
        if self.current_page <= 0:
            if not self.loop_pages:
                prev_button.hidden = True
                prev_button.label = prev_button._label
            else:
                prev_button.label = prev_button.loop_label
        elif self.current_page >= 0:
            prev_button.hidden = False
            prev_button.label = prev_button._label

        self.clear_items()

        if self.show_indicator:
            self.buttons[
                PaginatorButtonType.page_indicator
            ].label = f"{self.current_page + 1}/{self.page_count + 1}"

        for key, button in self.buttons.items():
            if key != PaginatorButtonType.page_indicator:
                if button.hidden:
                    button.disabled = True
                    if self.show_disabled:
                        self.add_item(button)
                else:
                    button.disabled = False
                    self.add_item(button)
            elif self.show_indicator:
                self.add_item(button)

        if self.show_menu:
            self.add_menu()

        # We're done adding standard buttons and menus, so we can now add any specified custom view items below them
        # The bot developer should handle row assignments for their view before passing it to Paginator
        if self.custom_view:
            self.update_custom_view(self.custom_view)

        return self.buttons

    def update_custom_view(self, custom_view: discord.ui.View):
        """Updates the custom view shown on the paginator."""
        if isinstance(self.custom_view, discord.ui.View):
            for item in self.custom_view.children:
                self.remove_item(item)
        for item in custom_view.children:
            self.add_item(item)

    def get_page_group_content(self, page_group: PageGroup) -> list[Page]:
        """Returns a converted list of `Page` objects for the given page group based on the content of its pages."""
        return [self.get_page_content(page) for page in page_group.pages]

    @staticmethod
    def get_page_content(
        page: Page | str | discord.Embed | list[discord.Embed],
    ) -> Page:
        """Converts a page into a :class:`Page` object based on its content."""
        if isinstance(page, Page):
            return page
        elif isinstance(page, str):
            return Page(content=page, embeds=[], files=[])
        elif isinstance(page, discord.Embed):
            return Page(content=None, embeds=[page], files=[])
        elif isinstance(page, discord.File):
            return Page(content=None, embeds=[], files=[page])
        elif isinstance(page, list):
            if all(isinstance(x, discord.Embed) for x in page):
                return Page(content=None, embeds=page, files=[])
            if all(isinstance(x, discord.File) for x in page):
                return Page(content=None, embeds=[], files=page)
            else:
                raise TypeError("All list items must be embeds or files.")
        else:
            raise TypeError(
                "Page content must be a Page object, string, an embed, a list of"
                " embeds, a file, or a list of files."
            )

    async def page_action(self, interaction: discord.Interaction | None = None) -> None:
        """Triggers the callback associated with the current page, if any.

        Parameters
        ----------
        interaction: Optional[:class:`discord.Interaction`]
            The interaction that was used to trigger the page action.
        """
        if self.get_page_content(self.pages[self.current_page]).callback:
            await self.get_page_content(self.pages[self.current_page]).callback(
                interaction=interaction
            )

    async def send(
        self,
        destination: discord.abc.Messageable,
        **kwargs,
    ) -> discord.Message:
        """Sends a message with the paginated items.

        Parameters
        ----------
        ctx: Union[:class:`~discord.ext.commands.Context`]
            A command's invocation context.
        target: Optional[:class:`~discord.abc.Messageable`]
            A target where the paginated message should be sent, if different from the original :class:`Context`
        target_message: Optional[:class:`str`]
            An optional message shown when the paginator message is sent elsewhere.
        reference: Optional[Union[:class:`discord.Message`, :class:`discord.MessageReference`, :class:`discord.PartialMessage`]]
            A reference to the :class:`~discord.Message` to which you are replying with the paginator.
            This can be created using :meth:`~discord.Message.to_reference` or passed directly as a
            :class:`~discord.Message`. You can control whether this mentions the author of the referenced message
            using the :attr:`~discord.AllowedMentions.replied_user` attribute of ``allowed_mentions`` or by
            setting ``mention_author``.
        allowed_mentions: Optional[:class:`~discord.AllowedMentions`]
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with :attr:`~discord.Client.allowed_mentions`.
            The merging behaviour only overrides attributes that have been explicitly passed
            to the object, otherwise it uses the attributes set in :attr:`~discord.Client.allowed_mentions`.
            If no object is passed at all then the defaults given by :attr:`~discord.Client.allowed_mentions`
            are used instead.
        mention_author: Optional[:class:`bool`]
            If set, overrides the :attr:`~discord.AllowedMentions.replied_user` attribute of ``allowed_mentions``.
        delete_after: Optional[:class:`float`]
            If set, deletes the paginator after the specified time.

        Returns
        -------
        :class:`~discord.Message`
            The message that was sent with the paginator.
        """

        page = self._prepare()

        self.message = await destination.send(
            **page,
            **kwargs,
        )

        return self.message

    @overload
    async def edit(
        self,
        message: discord.PartialMessage,
        **kwargs,
    ) -> discord.Message:
        ...

    @overload
    async def edit(
        self,
        message: discord.Message,
        **kwargs,
    ) -> discord.Message | None:
        ...

    @overload
    async def edit(
        self,
        message: discord.ApplicationContext | BridgeApplicationContext,
        **kwargs,
    ) -> discord.InteractionMessage:
        ...

    @overload
    async def edit(
        self,
        message: BridgeExtContext,
        **kwargs,
    ) -> discord.Message | None:
        ...

    @overload
    async def edit(
        self,
        message: discord.Interaction,
        **kwargs,
    ) -> discord.InteractionMessage | None:
        ...

    async def edit(
        self,
        message: discord.PartialMessage
        | discord.Message
        | discord.Interaction
        | discord.ApplicationContext
        | BridgeApplicationContext
        | BridgeExtContext,
        **kwargs,
    ) -> discord.Message | discord.InteractionMessage | None:
        """Edits an existing message to replace it with the paginator.

        .. note::

            If a view was previously present on the message, it will be removed.

        Parameters
        ----------
        message: Union[:class:`~discord.PartialMessage`, :class:`~discord.Message`, :class:`~discord.Interaction`, :class:`~discord.ApplicationContext`, :class:`~discord.ext.bridge.Context`]
            The message to edit with the paginator.

        Returns
        -------
        :class:`~discord.Message` | :class:`~discord.InteractionMessage` | ``None``
            The message that was edited. Returns ``None`` if the operation failed.
        """

        page = self._prepare()

        # pyright thinks the return type of this method can't be assigned to Message attribute for some reason
        self.message = await message.edit(  # type: ignore
            **page,
            attachments=[],
            **kwargs,
        )
        if self.message is None:
            if isinstance(message, discord.Interaction):
                # if the message is None, it means that interaction.response.edit_message was used.
                # this can only be done if the interaction was from a component or a modal (not a slash command)
                # both of which have the message attribute set if you can use edit_message
                self.message: discord.Message = message.message  # type: ignore
            elif isinstance(
                message, discord.Message
            ):  # isinstance check was added to satisfy type checker. this is the only other case that might return None
                # target was discord.Message, and edit was in-place
                self.message: discord.Message = message

        return self.message

    async def respond(
        self,
        interaction: discord.Interaction
        | discord.ApplicationContext
        | BridgeApplicationContext
        | BridgeExtContext,
        ephemeral: bool = False,
        **kwargs,
    ) -> discord.Message | discord.WebhookMessage:
        """Sends an interaction response or followup with the paginated items. This will use the `respond` method.

        Parameters
        ----------
        interaction: Union[:class:`discord.Interaction`, :class:`BridgeContext`]
            The interaction or BridgeContext which invoked the paginator.
            If passing a BridgeContext object, you cannot make this an ephemeral paginator.
        ephemeral: :class:`bool`
            Whether the paginator message and its components are ephemeral.
            If ``target`` is specified, the ephemeral message content will be ``target_message`` instead.

            .. warning::

                If your paginator is ephemeral, it cannot have a timeout
                longer than 15 minutes (and cannot be persistent).

        target: Optional[:class:`~discord.abc.Messageable`]
            A target where the paginated message should be sent,
            if different from the original :class:`discord.Interaction`
        target_message: :class:`str`
            The content of the interaction response shown when the paginator message is sent elsewhere.

        Returns
        -------
        Union[:class:`~discord.Message`, :class:`~discord.WebhookMessage`]
            The :class:`~discord.Message` or :class:`~discord.WebhookMessage` that was sent with the paginator.
        """

        if ephemeral and (self.timeout is None or self.timeout >= 900):
            raise ValueError(
                "paginator responses cannot be ephemeral if the paginator timeout is 15"
                " minutes or greater"
            )

        page = self._prepare()

        msg = await interaction.respond(
            **page,
            ephemeral=ephemeral,
            **kwargs,
        )

        if isinstance(msg, (discord.Message, discord.WebhookMessage)):
            self.message = msg
        elif isinstance(msg, discord.Interaction):
            self.message = (
                await msg.original_response()
            )  # TODO: Try avoid this and work with Interactions wherever possible

        return self.message
