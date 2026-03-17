from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Word(Base, TimestampMixin):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    phonetic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    forms: Mapped[dict] = mapped_column(JSON, default=dict)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    definitions: Mapped[list["Definition"]] = relationship(back_populates="word_ref", cascade="all, delete-orphan")
    etymology: Mapped["Etymology | None"] = relationship(
        back_populates="word_ref", cascade="all, delete-orphan", uselist=False
    )
    derivations: Mapped[list["Derivation"]] = relationship(
        back_populates="word_ref", cascade="all, delete-orphan", foreign_keys="Derivation.word_id"
    )
    related_words: Mapped[list["RelatedWord"]] = relationship(
        back_populates="word_ref", cascade="all, delete-orphan", foreign_keys="RelatedWord.word_id"
    )
    images: Mapped[list["WordImage"]] = relationship(back_populates="word_ref", cascade="all, delete-orphan")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="word_ref", cascade="all, delete-orphan")


class Definition(Base):
    __tablename__ = "definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    part_of_speech: Mapped[str] = mapped_column(String(64))
    meaning_en: Mapped[str] = mapped_column(Text)
    meaning_ja: Mapped[str] = mapped_column(Text)
    example_en: Mapped[str] = mapped_column(Text)
    example_ja: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    word_ref: Mapped[Word] = relationship(back_populates="definitions")


class Etymology(Base):
    __tablename__ = "etymologies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), unique=True, index=True)
    origin_word: Mapped[str | None] = mapped_column(String(128), nullable=True)
    origin_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    core_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    word_ref: Mapped[Word] = relationship(back_populates="etymology")
    component_items: Mapped[list["EtymologyComponentItem"]] = relationship(
        back_populates="etymology_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyComponentItem.sort_order, EtymologyComponentItem.id",
        primaryjoin="and_(EtymologyComponentItem.etymology_id==Etymology.id, EtymologyComponentItem.variant_id==None)",
        foreign_keys="[EtymologyComponentItem.etymology_id]",
    )
    branches: Mapped[list["EtymologyBranch"]] = relationship(
        back_populates="etymology_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyBranch.sort_order, EtymologyBranch.id",
    )
    variants: Mapped[list["EtymologyVariant"]] = relationship(
        back_populates="etymology_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyVariant.sort_order, EtymologyVariant.id",
    )
    language_chain_links: Mapped[list["EtymologyLanguageChainLink"]] = relationship(
        back_populates="etymology_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyLanguageChainLink.sort_order, EtymologyLanguageChainLink.id",
        primaryjoin="and_(EtymologyLanguageChainLink.etymology_id==Etymology.id, EtymologyLanguageChainLink.variant_id==None)",
        foreign_keys="[EtymologyLanguageChainLink.etymology_id]",
    )
    component_meanings: Mapped[list["EtymologyComponentMeaning"]] = relationship(
        back_populates="etymology_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyComponentMeaning.sort_order, EtymologyComponentMeaning.id",
        primaryjoin="and_(EtymologyComponentMeaning.etymology_id==Etymology.id, EtymologyComponentMeaning.variant_id==None)",
        foreign_keys="[EtymologyComponentMeaning.etymology_id]",
    )


class EtymologyBranch(Base):
    __tablename__ = "etymology_branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etymology_id: Mapped[int] = mapped_column(
        ForeignKey("etymologies.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(255))
    meaning_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meaning_ja: Mapped[str | None] = mapped_column(String(255), nullable=True)

    etymology_ref: Mapped[Etymology] = relationship(back_populates="branches")


class EtymologyVariant(Base):
    __tablename__ = "etymology_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etymology_id: Mapped[int] = mapped_column(
        ForeignKey("etymologies.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    etymology_ref: Mapped[Etymology] = relationship(back_populates="variants")
    component_items: Mapped[list["EtymologyComponentItem"]] = relationship(
        back_populates="variant_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyComponentItem.sort_order, EtymologyComponentItem.id",
    )
    language_chain_links: Mapped[list["EtymologyLanguageChainLink"]] = relationship(
        back_populates="variant_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyLanguageChainLink.sort_order, EtymologyLanguageChainLink.id",
    )
    component_meanings: Mapped[list["EtymologyComponentMeaning"]] = relationship(
        back_populates="variant_ref",
        cascade="all, delete-orphan",
        order_by="EtymologyComponentMeaning.sort_order, EtymologyComponentMeaning.id",
    )


class EtymologyLanguageChainLink(Base):
    __tablename__ = "etymology_language_chain_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etymology_id: Mapped[int] = mapped_column(
        ForeignKey("etymologies.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("etymology_variants.id", ondelete="CASCADE"), index=True, nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    lang: Mapped[str] = mapped_column(String(32))
    lang_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    word: Mapped[str] = mapped_column(String(128))
    relation: Mapped[str | None] = mapped_column(String(32), nullable=True)

    etymology_ref: Mapped[Etymology] = relationship(
        back_populates="language_chain_links",
        foreign_keys=[etymology_id],
    )
    variant_ref: Mapped["EtymologyVariant | None"] = relationship(
        back_populates="language_chain_links",
        foreign_keys=[variant_id],
    )


class EtymologyComponentMeaning(Base):
    __tablename__ = "etymology_component_meanings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etymology_id: Mapped[int] = mapped_column(
        ForeignKey("etymologies.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("etymology_variants.id", ondelete="CASCADE"), index=True, nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    component_text: Mapped[str] = mapped_column(String(128))
    meaning: Mapped[str] = mapped_column(Text)

    etymology_ref: Mapped[Etymology] = relationship(
        back_populates="component_meanings",
        foreign_keys=[etymology_id],
    )
    variant_ref: Mapped["EtymologyVariant | None"] = relationship(
        back_populates="component_meanings",
        foreign_keys=[variant_id],
    )


class Derivation(Base):
    __tablename__ = "derivations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    derived_word: Mapped[str] = mapped_column(String(128))
    part_of_speech: Mapped[str] = mapped_column(String(32))
    meaning_ja: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    linked_word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id", ondelete="SET NULL"), nullable=True)

    word_ref: Mapped[Word] = relationship(back_populates="derivations", foreign_keys=[word_id])


class RelatedWord(Base):
    __tablename__ = "related_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    related_word: Mapped[str] = mapped_column(String(128))
    relation_type: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
    linked_word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id", ondelete="SET NULL"), nullable=True)

    word_ref: Mapped[Word] = relationship(back_populates="related_words", foreign_keys=[word_id])


class WordImage(Base):
    __tablename__ = "word_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(512))
    prompt: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    word_ref: Mapped[Word] = relationship(back_populates="images")


class EtymologyComponent(Base, TimestampMixin):
    __tablename__ = "etymology_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_text: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    resolved_meaning: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wiktionary_meanings: Mapped[list[str]] = mapped_column(JSON, default=list)
    wiktionary_related_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    wiktionary_derived_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    wiktionary_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    component_items: Mapped[list["EtymologyComponentItem"]] = relationship(back_populates="component_ref")


class EtymologyComponentItem(Base):
    __tablename__ = "etymology_component_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    etymology_id: Mapped[int] = mapped_column(ForeignKey("etymologies.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("etymology_variants.id", ondelete="CASCADE"), index=True, nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    component_text: Mapped[str] = mapped_column(String(128))
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(32), default="root")
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("etymology_components.id", ondelete="SET NULL"), index=True, nullable=True
    )

    etymology_ref: Mapped[Etymology] = relationship(
        back_populates="component_items",
        foreign_keys=[etymology_id],
    )
    variant_ref: Mapped["EtymologyVariant | None"] = relationship(
        back_populates="component_items",
        foreign_keys=[variant_id],
    )
    component_ref: Mapped[EtymologyComponent | None] = relationship(back_populates="component_items")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        CheckConstraint(
            "(word_id IS NOT NULL AND component_text IS NULL AND component_id IS NULL) OR "
            "(word_id IS NULL AND (component_text IS NOT NULL OR component_id IS NOT NULL))",
            name="ck_chat_sessions_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True, nullable=True)
    component_text: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("etymology_components.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Word Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    word_ref: Mapped[Word | None] = relationship(back_populates="chat_sessions")
    component_ref: Mapped[EtymologyComponent | None] = relationship()
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session_ref", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session_ref: Mapped[ChatSession] = relationship(back_populates="messages")
