"""XconWriter — generates Cadence ``.xcon`` CS Schema XML files.

Phase XI P0-B (system_design.md A.2): the ``.xcon`` file is an XML document
conforming to the Cadence CS Schema.  Every block is populated from the
shared DesignConnectivity model:

  * lastids          — instance/net/instterm counts (same as con)
  * cells            — S cells with terms (direction full names)
  * nets             — N nets (id + internal name)
  * aliases          — local power net → global net
  * instances        — I instances with pins→connections
  * extensions       — netScopes (global nets) + pages (nets/instances refs)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .base import WriterBase
from .connectivity_model import DesignConnectivity
from .output_manager import OutputManager

logger = logging.getLogger(__name__)

#: term direction digit → full XML direction name (A.2.2)
_DIR_NAMES: dict[int, str] = {1: "input", 2: "output", 3: "inout"}


def _xml(text: str) -> str:
    """XML 转义（.xcon 是 XML，网络名/元件名含 ``&`` 等必须转义）。

    Cadence SPCOCD-553 根因之一：MARK 元件自动网络名如
    ``unnamed_22_mark_i73_&1`` 含裸 ``&`` → XML 解析失败
    （not well-formed）→ 加载 5015.xcon 报 syntax error。

    Args:
        text: 原始名称文本。

    Returns:
        XML 转义后的文本（``&``→``&amp;`` 等）。
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class XconWriter(WriterBase):
    """Generate a ``<cell>.xcon`` file from a DesignConnectivity model."""

    FORMAT_NAME: str = "xcon"

    def write(self, conn: "DesignConnectivity", output_dir: Path) -> list[Path]:
        """Generate and write the .xcon file.

        Args:
            conn: DesignConnectivity built by ConnectivityModelBuilder.
            output_dir: Output root directory.

        Returns:
            List containing the written .xcon path.
        """
        self._ensure_output_dir(output_dir)
        mgr = OutputManager(
            project_name=conn.cell_name,
            output_root=output_dir,
        )
        mgr.setup_directory_structure()
        content = self._build_xcon_content(conn)
        path = mgr.write_xcon(
            cell_name=conn.cell_name,
            library_alias=conn.library_alias,
            num_pages=len(conn.pages),
            content_override=content,
        )
        logger.info(
            "XconWriter: %d cells / %d nets / %d instances / %d pages → %s",
            conn.cell_count, conn.net_count,
            conn.instance_count, len(conn.pages), path,
        )
        return [path]

    def write_with_manager(
        self,
        conn: "DesignConnectivity",
        mgr: OutputManager,
    ) -> list[Path]:
        """Generate a .xcon file using an existing OutputManager."""
        content = self._build_xcon_content(conn)
        path = mgr.write_xcon(
            cell_name=conn.cell_name,
            library_alias=conn.library_alias,
            num_pages=len(conn.pages),
            content_override=content,
        )
        return [path]

    # ------------------------------------------------------------------
    #  Content builder
    # ------------------------------------------------------------------

    @classmethod
    def _build_xcon_content(cls, conn: "DesignConnectivity") -> str:
        """Build the complete .xcon XML content."""
        current_time: str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        lines: list[str] = []
        a = lines.append

        a('<schema xmlns="http://www.cadence.com/spb/csschema"')
        a('\txmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
        a('\txsi:schemaLocation="http://www.cadence.com/spb/csschema CSSchema002.xsd">')
        a("  <header>")
        a("    <schemaVersion>16.6</schemaVersion>")
        a("    <creatorTool>conceptHDL</creatorTool>")
        a("    <modifierTool>conceptHDL</modifierTool>")
        a(f"    <modificationTime>{current_time}</modificationTime>")
        a(f"    <savedLibrary>{_xml(conn.library_alias)}</savedLibrary>")
        a("  </header>")
        a("  <designs>")
        a(f'    <design schemaType="nameBased" name="{_xml(conn.cell_name)}" view="sch_1">')

        # ── lastids ─────────────────────────────────────────────────
        a("      <lastids>")
        a(f"        <instanceid>{conn.instance_count}</instanceid>")
        a(f"        <netid>{conn.net_count}</netid>")
        a(f"        <insttermid>{conn.pin_count}</insttermid>")
        a("      </lastids>")

        # ── cells ───────────────────────────────────────────────────
        a("      <cells>")
        for cell in conn.cells:
            a("        <cell>")
            a(f"          <id>{_xml(cell.cell_id)}</id>")
            a(f"          <library>{_xml(cell.library)}</library>")
            a(f"          <name>{_xml(cell.cell_name)}</name>")
            a(f"          <view>{_xml(cell.sym)}</view>")
            a("          <parameters>")
            a("          </parameters>")
            a("          <terms>")
            for term in cell.terms:
                dir_name = _DIR_NAMES.get(term.direction, "inout")
                a("            <term>")
                a(f"              <id>{_xml(term.term_id)}</id>")
                a(f"              <name>{_xml(term.name)}</name>")
                a(f"              <direction>{dir_name}</direction>")
                a("            </term>")
            a("          </terms>")
            a("        </cell>")
        a("      </cells>")

        # ── nets ────────────────────────────────────────────────────
        a("      <nets>")
        for net in conn.nets:
            a("        <net>")
            a(f"          <id>{_xml(net.net_id)}</id>")
            a(f"          <name>{_xml(net.internal_name)}</name>")
            a("        </net>")
        a("      </nets>")

        # ── aliases ─────────────────────────────────────────────────
        a("      <aliases>")
        for local_name, global_name in conn.aliases:
            local_rec = conn.net_by_internal.get(local_name)
            global_rec = conn.net_by_internal.get(global_name)
            if local_rec is None or global_rec is None:
                continue
            a(
                f'        <alias net1="{local_rec.net_id}" lsb1="-1" msb1="-1"'
                f' net2="{global_rec.net_id}" lsb2="-1" msb2="-1" />'
            )
        a("      </aliases>")
        a("      <differentialnets>")
        a("      </differentialnets>")
        a("      <differentialbusnets>")
        a("      </differentialbusnets>")
        a("      <netgroups>")
        a("      </netgroups>")
        a("      <netinterfaces>")
        a("      </netinterfaces>")

        # ── instances ───────────────────────────────────────────────
        a("      <instances>")
        for irec in conn.instances:
            a("        <instance>")
            a(f"          <id>{_xml(irec.inst_id)}</id>")
            a(f"          <cellid>{_xml(irec.cell_id)}</cellid>")
            a(f"          <name>{_xml(irec.internal_name)}</name>")
            a("          <parameters>")
            a("          </parameters>")
            a("          <masks>")
            a("          </masks>")
            a("          <powers>")
            a("          </powers>")
            a("          <pins>")
            for pre in irec.pins:
                a("            <pin>")
                a(f"              <id>{pre.pin_id}</id>")
                a(f"              <termid>{pre.term_id}</termid>")
                a("              <connections>")
                a(f"                <connection net=\"{pre.net_id}\" />")
                a("              </connections>")
                a("            </pin>")
            a("          </pins>")
            a("          <differentialpins>")
            a("          </differentialpins>")
            a("          <differentialbuspins>")
            a("          </differentialbuspins>")
            a("          <portgroups>")
            a("          </portgroups>")
            a("          <portinterfaces>")
            a("          </portinterfaces>")
            a("        </instance>")
        a("      </instances>")

        a("      <templateresolutions>")
        a("      </templateresolutions>")
        a("      <templateinstances>")
        a("      </templateinstances>")

        # ── extensions: netScopes + pages ───────────────────────────
        a("      <extensions>")
        a('        <extension name="schematic_extension">')
        a("        <schematicExtension>")
        a("        <netScopes>")
        for net in conn.nets:
            if net.scope != 2:
                continue
            a(f'          <netScope ref="{_xml(net.bare_name)}">')
            for page_num in net.pages:
                a(f'            <pageScope number="{page_num}">')
                a("              <scope>global</scope>")
                a("            </pageScope>")
            a("          </netScope>")
        a("        </netScopes>")
        a("        <pages>")
        for page_conn in conn.pages:
            page_num = page_conn.page_num
            a(f'          <page number="{page_num}">')
            a(f"            <physicalPageNumber>{page_num}</physicalPageNumber>")
            a("            <errorStatus>false</errorStatus>")
            a("            <nets>")
            for pnr in page_conn.nets:
                a(f'              <net ref="{_xml(pnr.bare_name)}"></net>')
            a("            </nets>")
            a("            <instances>")
            for irec in page_conn.instances:
                # page-local short name (i1, i2, ...)
                a(f'              <instance ref="i{irec.page_local_k}"></instance>')
            a("            </instances>")
            a("          </page>")
        a("        </pages>")
        a("      </schematicExtension>")
        a("        </extension>")
        a("      </extensions>")

        a("    </design>")
        a("  </designs>")
        a("</schema>")
        return "\n".join(lines) + "\n"


#: Backward-compatible alias (pre-Phase-XI uppercase name).
XCONWriter = XconWriter  # noqa: N816
