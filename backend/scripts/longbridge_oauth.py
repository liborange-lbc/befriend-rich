#!/usr/bin/env python3
"""Longbridge OAuth 授权脚本 — 在本地 Mac 运行一次即可。

Usage:
    # 第一步：注册 OAuth client（只需运行一次）
    python scripts/longbridge_oauth.py register

    # 第二步：浏览器授权（会自动打开浏览器）
    python scripts/longbridge_oauth.py authorize

    # 第三步：测试连接
    python scripts/longbridge_oauth.py test

    # 部署到服务器：把 token 目录同步过去
    python scripts/longbridge_oauth.py deploy
"""
import json
import subprocess
import sys
from pathlib import Path

CLIENT_ID_FILE = Path.home() / ".longbridge" / "openapi" / "client_id"
TOKEN_DIR = Path.home() / ".longbridge" / "openapi" / "tokens"


def register():
    """Register an OAuth 2.0 client with Longbridge."""
    import httpx

    resp = httpx.post(
        "https://openapi.longbridge.com/oauth2/register",
        json={
            "redirect_uris": ["http://localhost:60355/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "AnXing Portfolio Sync",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    client_id = data.get("client_id", "")
    if not client_id:
        print(f"注册失败: {data}")
        sys.exit(1)

    # Save client_id for later use
    CLIENT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLIENT_ID_FILE.write_text(client_id)

    print(f"OAuth client 注册成功!")
    print(f"  client_id: {client_id}")
    print(f"  已保存到: {CLIENT_ID_FILE}")
    print(f"\n下一步: python scripts/longbridge_oauth.py authorize")


def authorize():
    """Run browser-based OAuth authorization."""
    if not CLIENT_ID_FILE.exists():
        print("请先运行: python scripts/longbridge_oauth.py register")
        sys.exit(1)

    client_id = CLIENT_ID_FILE.read_text().strip()
    print(f"使用 client_id: {client_id}")
    print("正在启动浏览器授权...")

    from longbridge.openapi import Config, OAuthBuilder, TradeContext

    oauth = OAuthBuilder(client_id).build(
        lambda url: (
            print(f"\n请在浏览器中打开以下链接并授权:\n{url}\n"),
            __import__("webbrowser").open(url),
        )
    )
    config = Config.from_oauth(oauth)

    # Quick test
    ctx = TradeContext(config)
    resp = ctx.stock_positions()
    count = sum(len(ch.positions) for ch in resp)
    print(f"\n授权成功! 检测到 {count} 个持仓。")
    print(f"Token 已保存到: {TOKEN_DIR / client_id}")
    print(f"\n下一步: python scripts/longbridge_oauth.py deploy")


def test():
    """Test the connection with saved OAuth token."""
    if not CLIENT_ID_FILE.exists():
        print("请先运行 register 和 authorize")
        sys.exit(1)

    client_id = CLIENT_ID_FILE.read_text().strip()

    from longbridge.openapi import Config, OAuthBuilder, QuoteContext, TradeContext

    oauth = OAuthBuilder(client_id).build(lambda url: None)
    config = Config.from_oauth(oauth)

    trade_ctx = TradeContext(config)
    resp = trade_ctx.stock_positions()

    print("持仓列表:")
    for ch in resp:
        for pos in ch.positions:
            qty = pos.quantity
            print(f"  {pos.symbol} {pos.symbol_name}: {qty}股, 币种={pos.currency}, 成本={pos.cost_price}")

    # Test quotes
    symbols = [pos.symbol for ch in resp for pos in ch.positions if float(pos.quantity) > 0]
    if symbols:
        quote_ctx = QuoteContext(config)
        quotes = quote_ctx.quote(symbols[:10])
        print("\n实时报价:")
        for q in quotes:
            print(f"  {q.symbol}: 最新={q.last_done}")


def deploy():
    """Deploy OAuth token to remote server."""
    if not CLIENT_ID_FILE.exists():
        print("请先运行 register 和 authorize")
        sys.exit(1)

    client_id = CLIENT_ID_FILE.read_text().strip()
    token_path = TOKEN_DIR / client_id

    if not token_path.exists():
        print(f"Token 文件不存在: {token_path}")
        print("请先运行 authorize")
        sys.exit(1)

    server = "root@liborange.asia"
    remote_dir = "/root/.longbridge/openapi"

    print(f"正在同步到 {server}...")

    # Create remote directory
    subprocess.run(
        ["ssh", "-i", str(Path.home() / ".ssh/id_ed25519"), server,
         f"mkdir -p {remote_dir}/tokens"],
        check=True,
    )

    # Copy client_id
    subprocess.run(
        ["scp", "-i", str(Path.home() / ".ssh/id_ed25519"),
         str(CLIENT_ID_FILE), f"{server}:{remote_dir}/client_id"],
        check=True,
    )

    # Copy token file
    subprocess.run(
        ["scp", "-i", str(Path.home() / ".ssh/id_ed25519"),
         str(token_path), f"{server}:{remote_dir}/tokens/{client_id}"],
        check=True,
    )

    print("部署完成!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    cmds = {"register": register, "authorize": authorize, "test": test, "deploy": deploy}
    if cmd not in cmds:
        print(f"未知命令: {cmd}")
        print(f"可用命令: {', '.join(cmds)}")
        sys.exit(1)

    cmds[cmd]()
