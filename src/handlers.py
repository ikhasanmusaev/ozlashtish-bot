from telegraph import Telegraph

telegraph = Telegraph(access_token='0e1091ab7dacc5a12236177b70bbd426c822904a075efa5e22a4ffd7eff0')
l = ['1', '2', '3']
response = telegraph.create_page(
    "A'lochilar",
    html_content=f'<h3>Ro`yxat</h3> <p>{"<br>".join(l)}</p>'
)

print(response['url'])
