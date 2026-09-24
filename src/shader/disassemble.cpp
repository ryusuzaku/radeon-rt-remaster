#include <d3dcompiler.h>
#include <wrl/client.h>
#include <iostream>
#include <string>
#include <vector>
#include <cstdint>
#include <stdexcept>
// CPU-only diagnostic. Never creates a D3D device or GPU shader object.
int main() {
    try {
        std::string hex;char ch;
        while(std::cin.get(ch) && ch!='\n') {
            if(hex.size()>=32768)throw std::runtime_error("shader exceeds 16 KiB");
            hex+=ch;
        }
        if(std::cin.get(ch))throw std::runtime_error("trailing input");
        if(hex.empty()||hex.size()%8)throw std::runtime_error("unaligned shader hex");
        auto digit=[](char c)->unsigned {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("invalid hex");};
        std::vector<std::uint32_t> words(hex.size()/8);
        auto bytes=reinterpret_cast<unsigned char*>(words.data());
        for(std::size_t i=0;i<hex.size()/2;++i)bytes[i]=static_cast<unsigned char>((digit(hex[i*2])<<4)|digit(hex[i*2+1]));
        if(words.size()<2 || (words[0]>>16!=0xfffe && words[0]>>16!=0xffff) || words.back()!=0x0000ffff)
            throw std::runtime_error("not a bounded legacy shader program");
        Microsoft::WRL::ComPtr<ID3DBlob> result;
        auto hr=D3DDisassemble(words.data(),words.size()*4,0,nullptr,&result);
        if(FAILED(hr)||!result||result->GetBufferSize()>1024*1024)throw std::runtime_error("disassembly rejected");
        auto size=result->GetBufferSize();auto text=static_cast<const char*>(result->GetBufferPointer());
        if(size && text[size-1]=='\0')--size;
        std::cout.write(text,size);return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
