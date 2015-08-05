// Color Look Up Table Shader ==================================================

// Configuration ---------------------------------------------------------------

#define CLUT_ENABLED	1

// Key to toggle CLUT on or off. See MSDN, "Virtual-Key Codes",
// msdn.microsoft.com/library/windows/desktop/dd375731%28v=vs.85%29.aspx
// for a list of key codes.
#define CLUT_TOGGLEKEY	0x24	// 0x24 = HOME key

// END Configuration -----------------------------------------------------------

#pragma message "\nColor Look Up Table Shader ${VERSION}\n"
#pragma reshade showtogglemessage

texture2D ColorLookupTable_texColor : COLOR;

texture ColorLookupTable_texCLUT < string source = "ColorLookupTable.png"; >
{
	Width = ${WIDTH};
	Height = ${HEIGHT};
	Format = ${FORMAT};
};

sampler2D ColorLookupTable_samplerColor
{
	Texture = ColorLookupTable_texColor;
};

sampler2D ColorLookupTable_samplerCLUT
{
	Texture = ColorLookupTable_texCLUT;
};

void ColorLookupTable_VS(in uint id : SV_VertexID,
						 out float4 position : SV_Position,
						 out float2 texcoord : TEXCOORD0)
{
	texcoord.x = (id == 2) ? 2.0 : 0.0;
	texcoord.y = (id == 1) ? 2.0 : 0.0;
	position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

#define CLUTscale float2(1.0 / ${WIDTH}.0, 1.0 / ${HEIGHT}.0)

float4 ColorLookupTable_PS(in float4 position : SV_Position,
						   in float2 texcoord : TEXCOORD) : SV_Target
{
	float4 color = tex2D(ColorLookupTable_samplerColor, texcoord.xy);

	float3 CLUTcolor = float3((color.rg * (${HEIGHT} - 1) + 0.5) * CLUTscale,
							  color.b * (${HEIGHT} - 1));
	float shift = floor(CLUTcolor.z);
	CLUTcolor.x += shift * CLUTscale.y;
	CLUTcolor = lerp(tex2D(ColorLookupTable_samplerCLUT, CLUTcolor.xy).xyz,
					 tex2D(ColorLookupTable_samplerCLUT,
						   float2(CLUTcolor.x + CLUTscale.y, CLUTcolor.y)).xyz,
					 CLUTcolor.z - shift);
	color.rgb = lerp(color.rgb, CLUTcolor.xyz, 1.0);

	return color;
}

technique ColorLookupTable < bool enabled = CLUT_ENABLED; toggle = CLUT_TOGGLEKEY; >
{
	pass
	{
		VertexShader = ColorLookupTable_VS;
		PixelShader = ColorLookupTable_PS;
	}
}
